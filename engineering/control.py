"""Bound delivery effort to the frozen candidate; never grants merge authority."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time

PHASES = ('code-review', 'security-review', 'local-checks', 'remote-review-request')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def validate_preflight(report, manifest, compatibility_required):
    require(report.get('base') == manifest['base'] and report.get('digest') == manifest['digest'], 'Stale preflight')
    require(report.get('status') == 'PASS' and report.get('complete') is True, 'Incomplete preflight')
    rows = report.get('checks')
    require(isinstance(rows, list) and rows, 'Missing preflight checks')
    require(all(isinstance(r, dict) and type(r.get('exit_code')) is int and r['exit_code'] == 0
                and isinstance(r.get('evidence'), str) and r['evidence'].strip() for r in rows), 'Failed or unsubstantiated preflight')
    names = [r.get('name') for r in rows]
    require(len(names) == len(set(names)) and {'baseline', 'engineering-config', 'engineering-tests', 'tools'} <= set(names), 'Missing or duplicate preflight checks')
    if compatibility_required:
        require('consumer-compatibility' in names, 'Changed external adapter requires a real consumer probe')


def initialize(manifest, ledger, preflight, config, now):
    policy = config['process_control']
    validate_preflight(preflight, manifest, any(p in manifest['changed'] for p in policy['compatibility_paths']))
    return {'delivery_id': ledger['id'], 'base': ledger['base'], 'deadline': now + policy['max_wall_minutes'] * 60,
            'candidates': {}, 'failures': [], 'resolutions': {}, 'profile_sha256': hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()).hexdigest()}


def state_path(root, ledger):
    identity = ledger.get('id')
    require(isinstance(identity, str) and identity and all(ch.isalnum() or ch == '-' for ch in identity), 'Invalid delivery ID')
    return root / '.engineering/controls' / (identity + '.json')


def synchronize_base(plan, ledger, is_ancestor):
    """Consume only the same ledger's recorded, ancestry-verified base advances."""
    require(plan.get('delivery_id') == ledger['id'], 'Delivery control identity mismatch')
    current = plan['base']
    if current == ledger['base']:
        return
    changes = ledger.get('base_changes', [])
    start = next((i for i, row in enumerate(changes) if row.get('previous_base') == current), None)
    require(start is not None, 'Missing recorded base advance')
    for row in changes[start:]:
        require(row.get('previous_base') == current and row.get('reason') and is_ancestor(current, row.get('new_base')), 'Invalid base advance chain')
        current = row['new_base']
    require(current == ledger['base'], 'Incomplete base advance chain')
    plan['base'] = current


def verify(plan, manifest, ledger, config, now, *, check_resolutions=True):
    require(plan.get('delivery_id') == ledger['id'] and plan.get('base') == manifest['base'] == ledger['base'], 'Delivery control identity/base mismatch')
    require(plan.get('profile_sha256') == hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(), 'Delivery profile changed; resolve the existing plan explicitly')
    require(type(plan.get('deadline')) in (int, float) and now < plan['deadline'], 'Delivery wall-time budget expired')
    for fingerprint in {f['fingerprint'] for f in plan['failures']} if check_resolutions else set():
        failures = [f for f in plan['failures'] if f['fingerprint'] == fingerprint]
        if len(failures) >= 2:
            resolution = plan['resolutions'].get(fingerprint, {})
            require(resolution.get('failure_count') == len(failures) and resolution.get('base') == manifest['base']
                    and resolution.get('digest') == manifest['digest'], 'Repeated failure requires a changed strategy and passing current-candidate probe')


def reserve(plan, manifest, ledger, config, phase, now):
    verify(plan, manifest, ledger, config, now)
    require(phase in PHASES, 'Unknown costly phase')
    candidate = plan['candidates'].setdefault(manifest['digest'], {'preflight': None, 'phases': {}})
    require(candidate.get('preflight') is not None, 'Bind passing preflight before costly work')
    validate_preflight(candidate['preflight'], manifest, any(p in manifest['changed'] for p in config['process_control']['compatibility_paths']))
    require(phase not in candidate['phases'], 'Costly phase already reserved for this exact candidate; reuse its result or diagnose the interrupted run')
    candidate['phases'][phase] = {'reserved_at': now}


def verify_gate(root, manifest, ledger, config, *, include_remote=False):
    plan = json.loads(state_path(root, ledger).read_text(encoding='utf-8'))
    verify(plan, manifest, ledger, config, time.time())
    candidate = plan['candidates'].get(manifest['digest'], {})
    validate_preflight(candidate.get('preflight') or {}, manifest, any(p in manifest['changed'] for p in config['process_control']['compatibility_paths']))
    required = {'code-review', 'security-review', 'local-checks'}
    if include_remote:
        required.add('remote-review-request')
    require(required <= set(candidate.get('phases', {})), 'Mandatory costly-phase reservations missing')


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError('Delivery control is locked; inspect a possibly interrupted writer before continuing') from error
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink()


def main():
    import delivery as d
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bind', 'reserve', 'failure', 'strategy'])
    parser.add_argument('--preflight')
    parser.add_argument('--phase', choices=PHASES)
    parser.add_argument('--fingerprint')
    parser.add_argument('--cause')
    parser.add_argument('--evidence')
    parser.add_argument('--strategy')
    args = parser.parse_args()
    manifest = d.current_manifest(); config = d.read(d.ROOT / 'engineering/project.json')
    _branch, ledger_path = d.ledger_path(); ledger = d.read(ledger_path)
    path = state_path(d.ROOT, ledger)
    with locked(path.with_suffix('.lock')):
        if args.action == 'bind':
            require(args.preflight, 'Preflight report required')
            target = 'origin/' + config['default_branch']
            require(d.base_sha(target) == manifest['base'] and d.git('merge-base', 'HEAD', target).decode().strip() == manifest['base'], 'Candidate must start from the verified default-branch baseline')
            report = d.read(d.ROOT / args.preflight)
            validate_preflight(report, manifest, any(p in manifest['changed'] for p in config['process_control']['compatibility_paths']))
            require(all((d.ROOT / row['evidence']).is_file() for row in report['checks']), 'Preflight log/probe files must exist')
            plan = d.read(path) if path.exists() else initialize(manifest, ledger, report, config, time.time())
            synchronize_base(plan, ledger, lambda old, new: d.git('merge-base', '--is-ancestor', old, new) == b'')
            verify(plan, manifest, ledger, config, time.time(), check_resolutions=False)
            candidate = plan['candidates'].setdefault(manifest['digest'], {'phases': {}})
            require(not candidate['phases'], 'Preflight cannot be rewritten after costly work starts')
            candidate['preflight'] = report
        else:
            plan = d.read(path)
            verify(plan, manifest, ledger, config, time.time(), check_resolutions=args.action == 'reserve')
            if args.action == 'reserve':
                reserve(plan, manifest, ledger, config, args.phase, time.time())
            elif args.action == 'failure':
                require(all(isinstance(x, str) and x.strip() for x in [args.fingerprint, args.cause, args.evidence]), 'Failure needs stable cause fingerprint and actual evidence')
                require((d.ROOT / args.evidence).is_file(), 'Failure evidence missing')
                plan['failures'].append({'fingerprint': args.fingerprint, 'cause': args.cause, 'evidence': args.evidence, 'at': time.time()})
            else:
                require(args.fingerprint and args.strategy and args.strategy.strip() and args.evidence, 'Changed strategy and probe required')
                probe = d.read(d.ROOT / args.evidence)
                require(probe.get('status') == 'PASS' and probe.get('complete') is True and probe.get('digest') == manifest['digest']
                        and probe.get('base') == manifest['base'], 'Passing current-candidate probe required')
                count = sum(f['fingerprint'] == args.fingerprint for f in plan['failures'])
                require(count >= 2, 'No repeated failure for this fingerprint')
                plan['resolutions'][args.fingerprint] = {'strategy': args.strategy, 'probe': args.evidence, 'failure_count': count,
                                                       'base': manifest['base'], 'digest': manifest['digest']}
        temporary = path.with_suffix('.tmp')
        d.save(temporary, plan); os.replace(temporary, path)
    print(json.dumps({'status': 'PASS', 'action': args.action, 'digest': manifest['digest'],
                      'deadline': plan['deadline'], 'tokens_measured': None}))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        print('BLOCKED: ' + str(error))
        raise SystemExit(1)
