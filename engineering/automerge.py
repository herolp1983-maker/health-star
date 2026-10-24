"""Authorize exact-head automatic Squash merge from fresh, verified evidence.

No credentials, GitHub writes, implicit queueing or admin overrides live here.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from types import SimpleNamespace

import delivery as d

CORE_JOBS = {'Android Quality', 'Secrets', 'Static Security', 'Dependencies', 'Risk Detection'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def fresh(value, now, age, label):
    require(type(value) in {int, float} and 0 <= now - value <= age,
            f'{label} is missing, stale or future-dated')


def authorize(config, manifest, code, security, local, remote, rules, commit, *, now=None, repair_limit=2):
    now = time.time() if now is None else now
    require(config.get('merge_policy') == 'automatic-squash-exact-head', 'Automatic merge policy is not enabled')
    mode = config.get('gate_mode')
    require(mode in {'server-enforced', 'agent-verified'}, 'Unknown delivery gate mode')
    require(config.get('require_enforced_branch_rules') is (mode == 'server-enforced'),
            'Gate mode and branch-rule requirement conflict')
    require(re.fullmatch(r'[0-9a-f]{40}', commit) is not None, 'A complete reviewed commit SHA is required')
    for kind, report in [('code-review', code), ('security-review', security)]:
        d.validate_review(report, manifest, kind)
    require(local.get('base') == manifest['base'] and local.get('digest') == manifest['digest'], 'Local checks are stale')
    require(local.get('complete') is True and local.get('status') == 'PASS', 'Local checks are incomplete or failed')
    rows = local.get('checks', [])
    require(isinstance(rows, list) and all(isinstance(x, dict) for x in rows), 'Malformed local check evidence')
    require(all(type(x.get('exit_code')) is int and x['exit_code'] == 0 for x in rows),
            'A reported local check failed or has malformed exit evidence')
    for name in ['domain-tests', 'web-build', 'android-debug', 'engineering-config', 'engineering-tests']:
        matches = [x for x in rows if x.get('name') == name]
        require(len(matches) == 1 and type(matches[0].get('exit_code')) is int and matches[0]['exit_code'] == 0,
                f'Local check {name} did not pass exactly once')
    high_risk = bool(d.sensitive(manifest['changed']))
    if high_risk:
        require(config.get('high_risk_independent_security_review') is True, 'High-risk independent security review is mandatory')
        require(security['reviewer'].startswith(('subagent:', 'codex-exec:')) and security['reviewer'] != code['reviewer'],
                'HIGH-RISK requires distinct fresh code and security reviewers')
    fresh(remote.get('fetched_at'), now, 60, 'Remote PR/check evidence')
    fresh(rules.get('fetched_at'), now, 300, 'Effective rule evidence')
    repo, branch = config['repository'], config['default_branch']
    require(remote.get('repository') == repo and rules.get('repository') == repo, 'Repository evidence mismatch')
    require(remote.get('base_branch') == branch and rules.get('branch') == branch, 'Default branch evidence mismatch')
    require(type(remote.get('pr_number')) is int and remote['pr_number'] > 0, 'Invalid PR number')
    require(remote.get('state') == 'OPEN' and remote.get('draft') is False, 'PR is closed, merged or draft')
    require(remote.get('head_sha') == commit and remote.get('candidate_digest') == manifest['digest'], 'PR head/content differs from reviewed candidate')
    require(re.fullmatch(r'[0-9a-f]{40}', remote.get('base_sha', '')) is not None and remote['base_sha'] == remote.get('current_base_sha')
            and remote.get('up_to_date') is True, 'PR base moved or branch is not verified up-to-date')
    if manifest['base'] != remote['base_sha']:
        # Initial private-repo bootstrap can have a locally reconstructed root
        # commit. Its reviewed diff is equivalent only when both roots contain
        # the same exact Git tree, and the uploaded head tree is checked below.
        require(manifest.get('base_parent_count') == 0 and remote.get('base_parent_count') == 0
                and re.fullmatch(r'[0-9a-f]{40}', manifest.get('base_tree_sha', '')) is not None
                and manifest['base_tree_sha'] == remote.get('base_tree_sha')
                and remote.get('base_tree_verified') is True,
                'Reviewed diff does not start at an identical verified root baseline; earlier feature commits may be unreviewed')
    require(type(remote.get('unresolved_blocking_findings')) is int and remote['unresolved_blocking_findings'] == 0,
            'Blocking AI findings are unresolved or unknown')
    require(type(repair_limit) is int and repair_limit >= 2 and
            type(remote.get('fix_rounds')) is int and 0 <= remote['fix_rounds'] <= repair_limit,
            'Invalid global repair count')
    require(rules.get('source') in {'github-api', 'authenticated-github-ui'}, 'Untrusted rule evidence source')
    require(rules.get('verified') is True, 'Branch-rule inventory was not verified')
    if mode == 'server-enforced':
        for key in ['enforced', 'pull_request_required', 'strict']:
            require(rules.get(key) is True, f'Effective branch protection lacks {key}')
        require(rules.get('bypass_actors') == [], 'Rule bypasses are present or unknown')
    else:
        require(rules.get('enforced') is False and rules.get('server_enforcement_unavailable') is True,
                'Agent-verified mode requires explicit evidence that server enforcement is unavailable')
        require(rules.get('pull_request_required') is False and rules.get('strict') is False,
                'Agent-verified mode must not claim unenforced rules are active')
    require(type(rules.get('required_approving_reviews')) is int and rules['required_approving_reviews'] == 0,
            'Unexpected human approval requirement')
    required = config['required_jobs']
    require(isinstance(required, list) and all(isinstance(x, str) for x in required)
            and len(required) == len(set(required)) and CORE_JOBS <= set(required),
            'Configured mandatory CI omits core checks or is malformed')
    if mode == 'server-enforced':
        require(set(required) <= set(rules.get('required_checks', [])), 'Effective rules do not require all configured checks')
    else:
        require(rules.get('required_checks') == [], 'Unenforced rules must not be represented as required server checks')
    sources = rules.get('required_check_sources', {})
    require(isinstance(sources, dict), 'Malformed required-check sources')
    if mode == 'server-enforced':
        require(all(sources.get(name) == 'github-actions' for name in required),
                'Mandatory checks are not bound to the GitHub Actions app in effective rules')
    else:
        require(sources == {}, 'Unenforced check sources must not be represented as active protection')
    checks = remote.get('checks')
    require(isinstance(checks, list) and all(isinstance(x, dict) for x in checks), 'Malformed CI evidence')
    require(d.classify_checks(checks, required) == 'PASS', 'Mandatory CI is missing, pending, skipped, ambiguous or failed')
    for name in required:
        row = next(x for x in checks if x['name'] == name)
        require(row.get('head_sha') == commit and row.get('app_slug') == 'github-actions'
                and row.get('workflow_path') == '.github/workflows/engineering.yml',
                f'Check {name} has stale head or unverified workflow provenance')
    # An additional configured required check must pass too; do not ignore stronger existing rules.
    require(d.classify_checks(checks, rules['required_checks']) == 'PASS', 'An additional effective required check is not successful')
    for name in rules['required_checks']:
        row = next(x for x in checks if x['name'] == name)
        require(isinstance(sources.get(name), str) and sources[name] and row.get('app_slug') == sources[name]
                and row.get('head_sha') == commit, 'Additional required check provenance is missing or mismatched')
    return {'status': 'ELIGIBLE', 'gate_mode': mode, 'server_enforced': mode == 'server-enforced',
            'risk': 'HIGH-RISK' if high_risk else 'NORMAL',
            'repository_full_name': repo, 'pr_number': remote['pr_number'],
            'expected_head_sha': commit, 'merge_method': 'squash',
            'candidate_digest': manifest['digest'], 'authorized_at': now,
            'valid_until': min(remote['fetched_at'] + 60, rules['fetched_at'] + 300),
            'note': 'Re-fetch head immediately before the API call; verify merged state afterward.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--rules', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--remote-commit', help='Uploaded commit SHA when an identical root tree has a different local commit identity')
    args = parser.parse_args()
    commit = d.base_sha(args.commit)
    # This also checks the current tree, patch integrity and both review reports.
    d.gate(SimpleNamespace(staged=False, commit=commit))
    manifest = d.current_manifest()
    remote = d.read(d.ROOT / args.remote)
    remote_commit = args.remote_commit or commit
    local_tree = d.git('rev-parse', f'{commit}^{{tree}}').decode().strip()
    require(remote.get('head_tree_sha') == local_tree and remote.get('head_tree_verified') is True,
            'Uploaded PR head tree was not verified against the reviewed local commit')
    _branch, ledger_path = d.ledger_path()
    ledger = d.read(ledger_path)
    require(ledger.get('base') == manifest['base'] and ledger.get('fix_rounds') == remote.get('fix_rounds'),
            'Remote repair count does not match the persisted delivery ledger')
    plan = authorize(d.read(d.ROOT / 'engineering/project.json'), manifest,
                     d.read(d.CANDIDATE / 'code-review.json'), d.read(d.CANDIDATE / 'security-review.json'),
                     d.read(d.CANDIDATE / 'pre-delivery.json'), remote,
                     d.read(d.ROOT / args.rules), remote_commit, repair_limit=d.repair_limit(ledger))
    plan['delivery_id'] = ledger['id']
    d.save(d.EVIDENCE / 'merge-plan.json', plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        d.save(d.EVIDENCE / 'merge-plan.json', {'status': 'BLOCKED', 'reason': str(error)})
        print(f'BLOCKED: {error}', file=sys.stderr)
        sys.exit(1)
