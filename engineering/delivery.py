"""Deterministic local evidence and bounded GitHub observation; never merges/pushes."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / '.engineering'
CANDIDATE = EVIDENCE / 'candidate'
SEVERITIES = {'Critical', 'High', 'Medium', 'Low'}
SECRET_RULES = [
    ('private-key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('github-token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b')),
    ('provider-token', re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b')),
    ('aws-access-id', re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('literal-secret', re.compile(r'''(?i)(?:api[_-]?key|client[_-]?secret|storePassword|keyPassword)\s*[:=]\s*["'][A-Za-z0-9+/=_-]{20,}["']''')),
]
SENSITIVE = re.compile(
    r'(?i)(AndroidManifest\.xml$|(?:^|/)(?:auth\w*|migrations?|crypto\w*|secrets?|keys?)(?:/|\.)'
    r'|(?:health|vault|backup|storage|encrypt|credential|permission|login|session|native|ai-config|ai-results|ai-batch)'
    r'|(?:^|/)(?:\.github/|\.agents/|engineering/)|(?:^|/)AGENTS\.md$)')
FORBIDDEN = re.compile(
    r'(?i)(?:^|/)(?:\.keys|\.tools|\.engineering|\.engineering-tools|node_modules|build|dist|\.gradle|\.cache)(?:/|$)'
    r'|(?:^|/)(?:signing|local)\.properties$|\.(?:apk|aab|jks|keystore|p12|pem)$|(?:^|/)\.env(?:\.|$)')


def execute(args, *, cwd=ROOT, timeout=60, allowed=(0,)):
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout)
    if result.returncode not in allowed:
        # Do not echo commands/output which can include credentials or scanner hits.
        raise RuntimeError(f'{Path(str(args[0])).name} failed (exit {result.returncode}); inspect locally')
    return result.stdout


def git(*args):
    return execute(['git', *args])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def base_sha(value):
    return git('rev-parse', '--verify', '--end-of-options', value + '^{commit}').decode().strip()


def workspace_paths():
    return sorted(set(p.decode('utf-8') for p in git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0') if p))


def safe_file(path):
    candidate = ROOT / path
    if candidate.is_symlink():
        raise RuntimeError(f'Symlink requires explicit review before automation: {path}')
    if not candidate.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError('Path outside repository')
    return candidate


def inventory(untracked=None):
    result = {}
    modes = {}
    for row in git('ls-files', '--stage', '-z').split(b'\0'):
        if row:
            meta, path = row.split(b'\t', 1)
            mode, _oid, stage = meta.decode().split()
            if stage != '0':
                raise RuntimeError('Resolve Git conflicts before delivery')
            modes[path.decode()] = mode
    filemode = execute(['git', 'config', '--get', 'core.filemode'], allowed=(0, 1)).decode().strip() != 'false'
    paths = workspace_paths()
    if untracked is not None:
        tracked = set(p.decode() for p in git('ls-files', '-z', '--cached').split(b'\0') if p)
        paths = [p for p in paths if p in tracked or p in untracked]
    for path in paths:
        file = safe_file(path)
        if file.is_file():
            payload = file.read_bytes()
            # Use Git's normalized blob identity, respecting line-ending attributes.
            oid = git('hash-object', '--path=' + path, '--', path).decode().strip()
            mode = ('100755' if file.stat().st_mode & 0o111 else '100644') if filemode else modes.get(path, '100644')
            result[path] = {'blob': oid, 'mode': mode, 'bytes': len(payload)}
    return result


def tree_entries(base):
    result = {}
    for row in git('ls-tree', '-rz', base).split(b'\0'):
        if row:
            meta, rawpath = row.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            if kind != 'blob' or mode == '120000':
                raise RuntimeError('Submodules/symlinks require a separate reviewed delivery profile')
            result[rawpath.decode('utf-8')] = {'blob': oid, 'mode': mode}
    return result


def make_manifest(base, untracked=None):
    files = inventory(untracked)
    old = tree_entries(base)
    identity = {p: {'blob': item['blob'], 'mode': item['mode']} for p, item in files.items()}
    changed = sorted(p for p in old.keys() | files.keys() if old.get(p) != identity.get(p))
    digest = hashlib.sha256(json.dumps({'base': base, 'files': identity}, sort_keys=True).encode()).hexdigest()
    base_tree_sha = git('rev-parse', f'{base}^{{tree}}').decode().strip()
    base_parent_count = len(git('rev-list', '--parents', '-n', '1', base).decode().split()) - 1
    return {'base': base, 'base_tree_sha': base_tree_sha, 'base_parent_count': base_parent_count,
            'digest': digest, 'files': files, 'changed': changed}


def snapshot(args):
    base = base_sha(args.base)
    untracked = read(Path(args.untracked_paths)) if args.untracked_paths else []
    if not isinstance(untracked, list) or not all(isinstance(p, str) for p in untracked):
        raise RuntimeError('Untracked path selection must be a JSON string array')
    manifest = make_manifest(base, untracked)
    manifest['untracked_paths'] = untracked
    if forbidden_paths(manifest['changed']):
        raise RuntimeError('Forbidden candidate paths; do not export secrets or build artifacts to a reviewer')
    requirements = Path(args.requirements).read_text(encoding='utf-8')
    manifest['requirements_sha256'] = hashlib.sha256(requirements.encode()).hexdigest()
    manifest['digest'] = hashlib.sha256((manifest['digest'] + manifest['requirements_sha256']).encode()).hexdigest()
    # Keep binary payloads out of the text review patch. The manifest still binds
    # every file to its Git blob SHA and mode; reviewers can inspect binary files.
    patch = git('diff', '--no-ext-diff', '--no-textconv', base, '--').decode('utf-8', errors='replace')
    tracked = set(p.decode() for p in git('ls-files', '-z', '--cached').split(b'\0') if p)
    for path in manifest['changed']:
        if path not in tracked and path in manifest['files']:
            data = safe_file(path).read_bytes()
            if b'\0' in data:
                patch += f'\nBinary new file: {json.dumps(path)}; inspect the actual file.\n'
            else:
                patch += ''.join(difflib.unified_diff([], data.decode('utf-8', errors='replace').splitlines(keepends=True), fromfile='/dev/null', tofile='b/' + path))
    if len(patch.encode()) > 4_000_000:
        raise RuntimeError('Diff exceeds 4 MB; divide/review the full change explicitly, do not truncate')
    manifest['patch_sha256'] = hashlib.sha256(patch.encode()).hexdigest()
    CANDIDATE.mkdir(parents=True, exist_ok=True)
    (CANDIDATE / 'change.patch').write_bytes(patch.encode('utf-8'))
    (CANDIDATE / 'requirements.txt').write_text(requirements, encoding='utf-8')
    save(CANDIDATE / 'manifest.json', manifest)
    print(json.dumps({'base': base, 'digest': manifest['digest'], 'changed_files': len(manifest['changed'])}))


def current_manifest():
    saved = read(CANDIDATE / 'manifest.json')
    if hashlib.sha256((CANDIDATE / 'change.patch').read_bytes()).hexdigest() != saved['patch_sha256']:
        raise RuntimeError('Review patch changed; regenerate the snapshot and both reviews')
    current = make_manifest(saved['base'], saved['untracked_paths'])
    req = (CANDIDATE / 'requirements.txt').read_text(encoding='utf-8')
    reqhash = hashlib.sha256(req.encode()).hexdigest()
    current['digest'] = hashlib.sha256((current['digest'] + reqhash).encode()).hexdigest()
    if current['digest'] != saved['digest']:
        raise RuntimeError('Candidate or requirements changed; snapshot and repeat reviews')
    if current['base_tree_sha'] != saved.get('base_tree_sha') or current['base_parent_count'] != saved.get('base_parent_count'):
        raise RuntimeError('Reviewed base tree or ancestry changed; snapshot and repeat reviews')
    return saved


def validate_review(report, manifest, kind):
    if set(report) != {'status', 'base', 'digest', 'complete', 'reviewer', 'coverage', 'findings'}:
        raise RuntimeError(f'{kind}: malformed fields')
    if report['status'] != 'PASS' or report['complete'] is not True:
        raise RuntimeError(f'{kind}: incomplete or failed')
    if report['base'] != manifest['base'] or report['digest'] != manifest['digest']:
        raise RuntimeError(f'{kind}: stale evidence')
    if not isinstance(report['reviewer'], str) or not report['reviewer'].strip():
        raise RuntimeError(f'{kind}: missing reviewer identity')
    if kind == 'code-review' and not report['reviewer'].startswith(('subagent:', 'codex-exec:')):
        raise RuntimeError('code-review: independent context ID required')
    if not isinstance(report['coverage'], list) or not report['coverage'] or not all(isinstance(x, str) and x.strip() for x in report['coverage']):
        raise RuntimeError(f'{kind}: missing coverage')
    if not isinstance(report['findings'], list):
        raise RuntimeError(f'{kind}: malformed findings')
    for finding in report['findings']:
        if not isinstance(finding, dict) or set(finding) != {'severity', 'path', 'line', 'impact', 'fix'}:
            raise RuntimeError(f'{kind}: malformed finding')
        if finding['severity'] not in SEVERITIES or type(finding['line']) is not int or finding['line'] < 1:
            raise RuntimeError(f'{kind}: invalid severity/location')
        if not all(isinstance(finding[k], str) and finding[k].strip() for k in ['path', 'impact', 'fix']):
            raise RuntimeError(f'{kind}: missing finding detail')
        if finding['severity'] in {'Critical', 'High'}:
            raise RuntimeError(f'{kind}: unresolved {finding["severity"]}')


def forbidden_paths(paths):
    return [p for p in paths if FORBIDDEN.search(p) and not p.endswith('.env.example')]


def gate(args):
    manifest = current_manifest()
    for kind in ['code-review', 'security-review']:
        validate_review(read(CANDIDATE / (kind + '.json')), manifest, kind)
    if forbidden_paths(manifest['changed']):
        raise RuntimeError('Forbidden delivery paths; inspect candidate locally')
    git('diff', '--check', manifest['base'], '--')
    if args.staged:
        staged = {}
        for row in git('ls-files', '--stage', '-z').split(b'\0'):
            if row:
                meta, path = row.split(b'\t', 1)
                mode, blob, stage = meta.decode().split()
                if stage != '0':
                    raise RuntimeError('Unresolved index conflicts')
                staged[path.decode()] = {'blob': blob, 'mode': mode}
        if staged != {p: {'blob': row['blob'], 'mode': row['mode']} for p, row in manifest['files'].items()}:
            raise RuntimeError('Staged tree does not match reviewed candidate')
    if args.commit:
        committed = tree_entries(base_sha(args.commit))
        if committed != {p: {'blob': row['blob'], 'mode': row['mode']} for p, row in manifest['files'].items()}:
            raise RuntimeError('Committed tree does not match reviewed candidate')
    print('PASS: current independent review and security evidence; candidate content verified')


def sensitive(paths):
    def matches(path):
        relative = path.removeprefix('hero-health-android/').removeprefix('hero-health-prototype/')
        if re.search(r'\.(?:png|jpe?g|svg|webp|gif|ico|css)$', relative, re.I):
            return False
        return SENSITIVE.search(relative) or re.search(r'^(?:src/(?:model|AIFlows|AISettings|BatchAIForm|ai-results|ai-batch)\.|app/src/main/java/.*/(?:MainActivity|PdfActivity|AiService|AiHttp|AiProtocol)\.)', relative)
    return sorted(p for p in paths if matches(p))


def risk(args):
    paths = workspace_paths() if args.workspace else current_manifest()['changed']
    flagged = sensitive(paths)
    print(json.dumps({'risk': 'HIGH-RISK' if flagged else 'NORMAL', 'paths': flagged}, ensure_ascii=False, indent=2))


def secret_findings(text, path):
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for rule, pattern in SECRET_RULES:
            if pattern.search(line):
                fingerprint = hashlib.sha256((path + '\0' + rule + '\0' + line).encode()).hexdigest()
                findings.append({'severity': 'High', 'path': path, 'line': number, 'rule': rule, 'fingerprint': fingerprint})
    return findings


def patch_secret_findings(text, approved):
    """Adjudicate only exact synthetic literals added to their known source path.

    Removed lines and any other patch text retain their review-input identity and
    remain blocking. This prevents a broad test-file or diff exemption.
    """
    hits = secret_findings(text, '.engineering/candidate/change.patch')
    lines = text.splitlines()
    source_by_line = {}
    source = None
    for number, line in enumerate(lines, 1):
        if line.startswith('diff --git a/'):
            match = re.match(r'diff --git a/(.+) b/(.+)$', line)
            source = match.group(2) if match and match.group(1) == match.group(2) else None
        elif source and line.startswith('+') and not line.startswith('+++'):
            source_by_line[number] = source
    approved_keys = {(row['path'], row['rule'], row['fingerprint']) for row in approved}
    for hit in hits:
        source = source_by_line.get(hit['line'])
        if source and hit['rule'] == 'literal-secret':
            original = lines[hit['line'] - 1][1:]
            fingerprint = hashlib.sha256((source + '\0' + hit['rule'] + '\0' + original).encode()).hexdigest()
            if (source, hit['rule'], fingerprint) in approved_keys:
                hit.update(path=source, fingerprint=fingerprint, review_input='.engineering/candidate/change.patch')
    return hits


def adjudicate_fixtures(hits, entries):
    """Exact known synthetic literals only; never blanket-exempt tests or real token formats."""
    approved = {}
    for row in entries:
        if (row.get('rule') != 'literal-secret' or '/scripts/test-' not in row.get('path', '')
                or not re.fullmatch(r'[0-9a-f]{64}', row.get('fingerprint', '')) or not row.get('reason')):
            raise RuntimeError('Invalid synthetic fixture adjudication')
        approved[(row['path'], row['rule'], row['fingerprint'])] = row['reason']
    unresolved, adjudicated = [], []
    for hit in hits:
        reason = approved.get((hit['path'], hit['rule'], hit['fingerprint']))
        if reason:
            adjudicated.append({**hit, 'classification': 'VERIFIED_SYNTHETIC_FIXTURE', 'reason': reason})
        else:
            unresolved.append(hit)
    return unresolved, adjudicated


def security(args):
    manifest = None if args.workspace else current_manifest()
    paths = workspace_paths() if args.workspace else manifest['changed']
    hits, rules = [], []
    fixture_file = ROOT / 'engineering/secret-fixtures.json'
    fixtures = read(fixture_file) if fixture_file.exists() else []
    if manifest:
        # Removed lines and requirements are also review inputs: never send them unchecked.
        hits.extend(patch_secret_findings((CANDIDATE / 'change.patch').read_text(encoding='utf-8'), fixtures))
        hits.extend(secret_findings((CANDIDATE / 'requirements.txt').read_text(encoding='utf-8'), '.engineering/candidate/requirements.txt'))
    signals = [
        ('tls-bypass', r'onReceivedSslError|HostnameVerifier|checkServerTrusted'),
        ('cleartext', r'(?:usesCleartextTraffic|cleartextTrafficPermitted)\s*=\s*"true"|http://'),
        ('webview-access', r'setJavaScriptEnabled|setAllowFileAccess|setAllowUniversalAccessFromFileURLs'),
        ('sensitive-storage-or-log', r'SharedPreferences|localStorage|Log\.[diwev]\(|console\.(?:log|error)'),
        ('exported-or-intent', r'android:exported\s*=\s*"true"|getIntent\('),
    ]
    for path in paths:
        file = safe_file(path)
        if not file.is_file():
            continue
        data = file.read_bytes()
        if len(data) > 5_000_000:
            raise RuntimeError(f'File too large for local scanner; explicit coverage needed: {path}')
        if b'\0' in data:
            continue
        text = data.decode('utf-8', errors='replace')
        hits.extend(secret_findings(text, path))
        if re.search(r'\.(?:java|kt|tsx?|xml)$', path):
            for number, line in enumerate(text.splitlines(), 1):
                for rule, pattern in signals:
                    if re.search(pattern, line):
                        rules.append({'rule': rule, 'path': path, 'line': number, 'verdict': 'NEEDS_SEMANTIC_REVIEW'})
    hits, adjudicated = adjudicate_fixtures(hits, fixtures)
    result = {'status': 'FAIL' if hits else 'SEMANTIC_REVIEW_REQUIRED', 'automated_scope': 'heuristic-current-files-and-review-inputs',
              'gitleaks_available': bool(shutil.which('gitleaks')), 'history_scanned': False,
              'base': manifest['base'] if manifest else None, 'digest': manifest['digest'] if manifest else None,
              'secret_findings_redacted': hits, 'adjudicated_synthetic_fixtures': adjudicated, 'signals': rules, 'high_risk_paths': sensitive(paths)}
    save(EVIDENCE / 'security-static.json', result)
    print(json.dumps({'status': result['status'], 'secret_count': len(hits), 'semantic_signals': len(rules), 'report': '.engineering/security-static.json'}))
    if hits:
        raise RuntimeError('Potential secrets detected; values redacted, inspect files locally')


def repair_limit(ledger):
    """Keep the default cap unless this delivery records explicit user consent."""
    exception = ledger.get('repair_exception')
    if exception is None:
        return 2
    if not isinstance(exception, dict) or exception.get('delivery_id') != ledger.get('id') or \
            type(exception.get('max_rounds')) is not int or exception['max_rounds'] < 3 or \
            exception.get('approved_by') != 'user' or exception.get('scope') != 'this delivery only' or \
            not isinstance(exception.get('approval'), str) or not exception['approval'].strip() or \
            type(exception.get('approved_utc')) not in (int, float) or exception['approved_utc'] <= 0:
        raise RuntimeError('Malformed user-authorized repair exception')
    return exception['max_rounds']


def reserve_fix(ledger, reason):
    limit = repair_limit(ledger)
    if type(ledger.get('fix_rounds')) is not int or not 0 <= ledger['fix_rounds'] < limit:
        raise RuntimeError(f'Global {limit}-batch repair budget exhausted or invalid')
    if not reason.strip():
        raise RuntimeError('A repair reason is required')
    ledger['fix_rounds'] += 1
    ledger['fixes'].append({'round': ledger['fix_rounds'], 'reason': reason, 'reserved_utc': time.time()})
    return ledger


def ledger_path():
    branch = git('symbolic-ref', '--short', 'HEAD').decode().strip()
    config = read(ROOT / 'engineering/project.json')
    if branch in config['protected_branches']:
        raise RuntimeError('Default/protected branch cannot be delivered')
    base_sha('HEAD')
    return branch, EVIDENCE / 'ledgers' / (hashlib.sha256(branch.encode()).hexdigest() + '.json')


def ledger(args):
    branch, path = ledger_path()
    if args.command == 'start':
        base = base_sha(args.base)
        if path.exists():
            item = read(path)
            if item['base'] != base:
                raise RuntimeError('Existing ledger base differs; do not silently reset the repair budget')
        else:
            item = {'id': str(uuid.uuid4()), 'branch': branch, 'base': base, 'fix_rounds': 0, 'fixes': []}
            save(path, item)
    elif args.command == 'advance-base':
        item = read(path)
        new_base = base_sha(args.base)
        config = read(ROOT / 'engineering/project.json')
        if not args.reason.strip() or type(item.get('fix_rounds')) is not int or not 0 <= item['fix_rounds'] <= repair_limit(item):
            raise RuntimeError('Invalid base advance reason or persisted repair count')
        if new_base != base_sha('origin/' + config['default_branch']):
            raise RuntimeError('New review base must match the fetched default branch')
        git('merge-base', '--is-ancestor', item['base'], new_base)
        git('merge-base', '--is-ancestor', new_base, 'HEAD')
        if new_base != item['base']:
            item.setdefault('base_changes', []).append({'previous_base': item['base'], 'new_base': new_base,
                                                       'reason': args.reason, 'utc': time.time()})
            item['base'] = new_base
            save(path, item)
    else:
        item = reserve_fix(read(path), args.reason)
        save(path, item)
    print(json.dumps(item, ensure_ascii=False, indent=2))


def classify_checks(checks, required):
    """Every configured job must have exactly one completed SUCCESS result."""
    if not isinstance(checks, list) or not checks:
        return 'PENDING'
    by_name = {}
    for check in checks:
        by_name.setdefault(check.get('name'), []).append(check)
    pending = False
    for name in required:
        matches = by_name.get(name, [])
        if not matches:
            pending = True
            continue
        if len(matches) != 1:
            return 'FAIL'
        row = matches[0]
        if row.get('status') != 'COMPLETED':
            pending = True
        elif row.get('conclusion') != 'SUCCESS':
            return 'FAIL'
    return 'PENDING' if pending else 'PASS'


def ci_wait(args):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', args.repo) or not re.fullmatch(r'[0-9a-f]{40}', args.head):
        raise RuntimeError('Explicit repository and full candidate head SHA required')
    if not shutil.which('gh'):
        raise RuntimeError('gh unavailable: use connected GitHub tools with the same deadline')
    config = read(ROOT / 'engineering/project.json')
    # Persistent wall-clock deadline survives subprocess reruns after repair/push.
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', args.invocation):
        raise RuntimeError('Stable invocation ID required; reuse it after repair/push')
    waitfile = EVIDENCE / f'wait-{args.repo.replace("/", "-")}-{args.pr}-{args.invocation}.json'
    if waitfile.exists():
        deadline = read(waitfile)['deadline']
    else:
        deadline = time.time() + 480
        save(waitfile, {'deadline': deadline, 'pr': args.pr, 'repo': args.repo})
    mono_end = time.monotonic() + max(0, min(480, deadline - time.time()))
    state = 'PENDING'
    while time.monotonic() < mono_end:
        remaining = mono_end - time.monotonic()
        if remaining < 1:
            break
        try:
            raw = execute(['gh', 'pr', 'view', str(args.pr), '--repo', args.repo, '--json', 'headRefOid,statusCheckRollup'], timeout=min(30, remaining))
            result = json.loads(raw)
            if result['headRefOid'] != args.head:
                raise RuntimeError('PR head changed; cannot reuse old CI evidence')
            rows = [{'name': x.get('name'), 'status': x.get('status'), 'conclusion': x.get('conclusion')} for x in result.get('statusCheckRollup') or []]
            state = classify_checks(rows, config['required_jobs'])
            if state != 'PENDING':
                break
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            state = 'PENDING'
        remaining = mono_end - time.monotonic()
        if remaining > 0:
            time.sleep(min(30, remaining))
    print(json.dumps({'ci': state, 'head': args.head, 'recheck': f'gh pr checks {args.pr} --repo {args.repo}'}))
    return 0 if state == 'PASS' else (2 if state == 'PENDING' else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    snap = sub.add_parser('snapshot'); snap.add_argument('--base', required=True); snap.add_argument('--requirements', required=True); snap.add_argument('--untracked-paths', help='JSON array of explicitly approved new files; default excludes all untracked files')
    check = sub.add_parser('gate'); check.add_argument('--commit'); check.add_argument('--staged', action='store_true')
    for name in ['risk', 'security']:
        sub.add_parser(name).add_argument('--workspace', action='store_true')
    start = sub.add_parser('start'); start.add_argument('--base', required=True)
    advance = sub.add_parser('advance-base'); advance.add_argument('--base', required=True); advance.add_argument('--reason', required=True)
    sub.add_parser('fix').add_argument('--reason', required=True)
    wait = sub.add_parser('ci-wait'); wait.add_argument('--repo', required=True); wait.add_argument('--pr', type=int, required=True); wait.add_argument('--head', required=True); wait.add_argument('--invocation', required=True)
    args = parser.parse_args()
    return {'snapshot': snapshot, 'gate': gate, 'risk': risk, 'security': security, 'start': ledger, 'fix': ledger, 'advance-base': ledger, 'ci-wait': ci_wait}[args.command](args) or 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
