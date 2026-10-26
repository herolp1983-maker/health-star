"""Observe CI with no model calls or merge writes; token stays in environment."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler


def evaluate(snapshot, required, head, deadline, now):
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        return 'BLOCKED'
    if now >= deadline:
        return 'EXPIRED'
    if snapshot.get('source') != 'github-api' or snapshot.get('head_sha') != head:
        return 'BLOCKED'
    stamp = snapshot.get('fetched_at')
    if type(stamp) not in (int, float) or not 0 <= now - stamp <= 300:
        return 'BLOCKED'
    rows = snapshot.get('checks')
    if not isinstance(rows, list) or not rows:
        return 'PENDING'
    if not all(isinstance(row, dict) for row in rows):
        return 'BLOCKED'
    pending = False
    for name in required:
        matches = [r for r in rows if isinstance(r, dict) and r.get('name') == name]
        if not matches:
            pending = True
            continue
        if len(matches) != 1:
            return 'BLOCKED'
        row = matches[0]
        if row.get('head_sha') != head or row.get('app_slug') != 'github-actions':
            return 'BLOCKED'
        if row.get('status') == 'completed':
            if row.get('conclusion') != 'success':
                return 'FAILURE'
        elif row.get('status') not in {'queued', 'in_progress', 'waiting', 'pending', 'requested'}:
            return 'BLOCKED'
        else:
            pending = True
    return 'PENDING' if pending else 'SUCCESS'


def observe(previous, snapshot, required, head, deadline, now):
    if previous and (previous.get('head_sha') != head or previous.get('deadline') != deadline):
        raise RuntimeError('Observer identity/deadline changed; do not silently reset follow-up')
    status = evaluate(snapshot, required, head, deadline, now)
    changed = not previous or previous['status'] != status
    return {'head_sha': head, 'deadline': deadline, 'status': status, 'updated_at': now,
            'notify': changed and status in {'SUCCESS', 'FAILURE', 'BLOCKED', 'EXPIRED'},
            'merge_authorized': False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(path, token, timeout):
    request = Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'})
    with build_opener(NoRedirect).open(request, timeout=timeout) as response:
        raw = response.read(2_097_153)
        if len(raw) > 2_097_152:
            raise RuntimeError('GitHub response exceeds bounded observer size')
        return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', help='Authenticated connector snapshot; no network calls')
    parser.add_argument('--repository')
    parser.add_argument('--pr', type=int)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'engineering/project.json').read_text())
    import delivery as d
    from control import state_path
    _branch, ledger_path = d.ledger_path()
    ledger = d.read(ledger_path)
    plan = json.loads(state_path(root, ledger).read_text())
    if plan.get('delivery_id') != ledger['id'] or plan.get('base') != ledger['base']:
        raise RuntimeError('Observer delivery identity/base mismatch')
    if not re.fullmatch('[0-9a-f]{40}', args.head):
        raise RuntimeError('Exact head SHA required')
    path = state_path(root, ledger).parent / (ledger['id'] + '-observer-' + args.head + '.json')
    previous = json.loads(path.read_text()) if path.exists() else None
    token = os.environ.get('GITHUB_TOKEN')
    if not args.snapshot and (not token or not args.repository or not args.pr):
        print(json.dumps({'status': 'UNAVAILABLE', 'reason': 'Set authorized GITHUB_TOKEN for script polling; connector credentials are not exported. Use bounded connector fallback.', 'merge_authorized': False}))
        return 3
    if not args.snapshot and (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository) or args.pr <= 0):
        raise RuntimeError('Invalid repository/PR')
    while True:
        now = time.time()
        if args.snapshot:
            snapshot = json.loads(Path(args.snapshot).read_text())
        elif now >= plan['deadline']:
            snapshot = {}
        else:
            timeout = max(1, min(20, plan['deadline'] - now))
            pr = fetch(f'/repos/{args.repository}/pulls/{args.pr}', token, timeout)
            if pr.get('state') != 'open' or pr.get('head', {}).get('sha') != args.head:
                snapshot = {'head_sha': 'changed-or-closed'}
            else:
                data = fetch(f'/repos/{args.repository}/commits/{args.head}/check-runs?per_page=100', token, timeout)
                if data.get('total_count', 101) > 100:
                    raise RuntimeError('Check inventory exceeds observer bound; query through connector')
                snapshot = {'source': 'github-api', 'head_sha': args.head, 'fetched_at': time.time(),
                            'checks': [{**r, 'app_slug': r.get('app', {}).get('slug')} for r in data['check_runs']]}
        result = observe(previous, snapshot, config['required_jobs'], args.head, plan['deadline'], time.time())
        temporary = path.with_suffix('.tmp'); temporary.write_text(json.dumps(result, indent=2)); os.replace(temporary, path)
        if result['notify'] or args.snapshot:
            print(json.dumps(result))
        if args.snapshot or result['status'] != 'PENDING':
            return 0 if result['status'] in {'SUCCESS', 'PENDING'} else 1
        previous = result
        time.sleep(max(0, min(config['ci_poll_seconds'], plan['deadline'] - time.time())))


if __name__ == '__main__':
    try:
        from control import locked
        with locked(Path(__file__).resolve().parents[1] / '.engineering/watcher.lock'):
            raise SystemExit(main())
    except HTTPError as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': 'GitHub HTTP ' + str(error.code), 'merge_authorized': False}))
        raise SystemExit(1)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        print(json.dumps({'status': 'BLOCKED', 'reason': 'Observer input/auth/network failure; inspect saved evidence without printing credentials', 'merge_authorized': False}))
        raise SystemExit(1)
