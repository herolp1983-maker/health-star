import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import automerge
import delivery as d


class AutomaticMergeTests(unittest.TestCase):
    def setUp(self):
        self.now = 10000
        self.sha = 'a' * 40
        self.config = {'merge_policy': 'automatic-squash-exact-head', 'gate_mode': 'server-enforced', 'require_enforced_branch_rules': True,
                       'high_risk_independent_security_review': True, 'repository': 'owner/repo', 'default_branch': 'main',
                       'required_jobs': ['Android Quality', 'Secrets', 'Static Security', 'Dependencies', 'Risk Detection']}
        self.manifest = {'base': 'b' * 40, 'digest': 'content', 'changed': ['src/view.tsx']}
        self.code = {'status': 'PASS', 'base': self.manifest['base'], 'digest': 'content', 'complete': True,
                     'reviewer': 'subagent:code-session', 'coverage': ['all changed code'], 'findings': []}
        self.security = {**self.code, 'reviewer': 'subagent:security-session'}
        self.local = {'status': 'PASS', 'base': self.manifest['base'], 'digest': 'content', 'complete': True,
                      'checks': [{'name': n, 'exit_code': 0} for n in ['domain-tests', 'web-build', 'android-debug', 'engineering-config', 'engineering-tests']]}
        self.remote = {'repository': 'owner/repo', 'pr_number': 1, 'state': 'OPEN', 'draft': False, 'base_branch': 'main',
                       'head_sha': self.sha, 'base_sha': 'b' * 40, 'current_base_sha': 'b' * 40, 'up_to_date': True,
                       'candidate_digest': 'content', 'fetched_at': self.now, 'unresolved_blocking_findings': 0, 'fix_rounds': 2,
                       'checks': [{'name': n, 'head_sha': self.sha, 'status': 'COMPLETED', 'conclusion': 'SUCCESS',
                                   'app_slug': 'github-actions', 'workflow_path': '.github/workflows/engineering.yml'}
                                  for n in self.config['required_jobs']]}
        self.rules = {'repository': 'owner/repo', 'branch': 'main', 'verified': True, 'enforced': True,
                      'pull_request_required': True, 'strict': True, 'required_approving_reviews': 0,
                      'bypass_actors': [], 'required_checks': list(self.config['required_jobs']),
                      'required_check_sources': {name: 'github-actions' for name in self.config['required_jobs']},
                      'fetched_at': self.now, 'source': 'github-api'}

    def decide(self):
        return automerge.authorize(self.config, self.manifest, self.code, self.security, self.local,
                                   self.remote, self.rules, self.sha, now=self.now)

    def test_complete_current_evidence_authorizes_only_exact_sha_squash(self):
        plan = self.decide()
        self.assertEqual(plan['status'], 'ELIGIBLE')

    def test_fourth_batch_still_requires_its_own_explicit_limit(self):
        self.remote['fix_rounds'] = 4
        with self.assertRaises(RuntimeError):
            automerge.authorize(self.config, self.manifest, self.code, self.security,
                                self.local, self.remote, self.rules, self.sha,
                                now=self.now, repair_limit=3)
        plan = automerge.authorize(self.config, self.manifest, self.code, self.security,
                                   self.local, self.remote, self.rules, self.sha,
                                   now=self.now, repair_limit=4)
        self.assertEqual(plan['status'], 'ELIGIBLE')
        self.assertEqual(plan['expected_head_sha'], self.sha)
        self.assertEqual(plan['merge_method'], 'squash')
        self.assertNotIn('admin', plan)

    def test_third_batch_requires_explicit_bound_limit(self):
        self.remote['fix_rounds'] = 3
        with self.assertRaises(RuntimeError):
            self.decide()
        plan = automerge.authorize(self.config, self.manifest, self.code, self.security,
                                   self.local, self.remote, self.rules, self.sha,
                                   now=self.now, repair_limit=3)
        self.assertEqual(plan['status'], 'ELIGIBLE')

    def test_agent_verified_free_private_repository_requires_real_checks_and_honest_rules(self):
        self.config.update(gate_mode='agent-verified', require_enforced_branch_rules=False)
        self.rules.update(enforced=False, server_enforcement_unavailable=True,
                          pull_request_required=False, strict=False, required_checks=[],
                          required_check_sources={})
        plan = self.decide()
        self.assertEqual(plan['gate_mode'], 'agent-verified')
        self.assertFalse(plan['server_enforced'])
        self.remote['checks'][0]['conclusion'] = 'FAILURE'
        with self.assertRaises(RuntimeError):
            self.decide()
        self.remote['checks'][0]['conclusion'] = 'SUCCESS'
        self.rules['server_enforcement_unavailable'] = None
        with self.assertRaises(RuntimeError):
            self.decide()

    def test_reconstructed_root_baseline_requires_verified_exact_tree_and_root_ancestry(self):
        self.manifest.update(base_tree_sha='d' * 40, base_parent_count=0)
        self.remote.update(base_sha='e' * 40, current_base_sha='e' * 40,
                           base_tree_sha='d' * 40, base_parent_count=0, base_tree_verified=True)
        self.assertEqual(self.decide()['status'], 'ELIGIBLE')
        for changes in [{'base_tree_sha': 'f' * 40}, {'base_parent_count': 1},
                        {'base_tree_verified': False}, {'current_base_sha': 'f' * 40}]:
            old = copy.deepcopy(self.remote)
            self.remote.update(changes)
            with self.assertRaises(RuntimeError):
                self.decide()
            self.remote = old
        self.manifest['base_parent_count'] = 1
        with self.assertRaises(RuntimeError):
            self.decide()

    def test_disabled_unenforced_bypassable_or_incomplete_rules_block(self):
        baseline = copy.deepcopy(self.rules)
        for changes in [{'enforced': False}, {'verified': False}, {'strict': False}, {'bypass_actors': ['admin']},
                        {'required_checks': ['Build']}, {'required_approving_reviews': 1}, {'source': 'pr-file'},
                        {'required_check_sources': {}}, {'required_check_sources': {'Build': 'any-source', 'Secrets': 'github-actions'}}]:
            self.rules = {**baseline, **changes}
            with self.assertRaises(RuntimeError):
                self.decide()

    def test_moved_head_or_base_and_missing_ai_findings_evidence_block(self):
        baseline = copy.deepcopy(self.remote)
        for changes in [{'head_sha': 'c' * 40}, {'candidate_digest': 'old'}, {'current_base_sha': 'd' * 40},
                        {'up_to_date': False}, {'unresolved_blocking_findings': None}, {'unresolved_blocking_findings': 1},
                        {'draft': True}, {'state': 'CLOSED'}, {'repository': 'other/repo'}, {'fix_rounds': 3}]:
            self.remote = {**baseline, **changes}
            with self.assertRaises(RuntimeError):
                self.decide()

    def test_stale_or_future_evidence_blocks(self):
        for target, stamp in [(self.remote, self.now - 61), (self.rules, self.now - 301), (self.remote, self.now + 1)]:
            before = target['fetched_at']; target['fetched_at'] = stamp
            with self.assertRaises(RuntimeError):
                self.decide()
            target['fetched_at'] = before

    def test_reviewing_only_a_feature_intermediate_commit_cannot_cover_whole_pr(self):
        with tempfile.TemporaryDirectory(prefix='automerge-base-fixture-') as temp:
            root = Path(temp)
            def run(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            run('init', '-b', 'main'); run('config', 'user.name', 'Fixture'); run('config', 'user.email', 'fixture@example.invalid')
            (root / 'README.md').write_text('baseline\n'); run('add', '.'); run('commit', '-m', 'test: base')
            base = run('rev-parse', 'HEAD').decode().strip()
            run('switch', '-c', 'codex/feature')
            (root / 'earlier.txt').write_text('first feature commit, omitted by a partial diff\n')
            run('add', '.'); run('commit', '-m', 'test: first feature change')
            intermediate = run('rev-parse', 'HEAD').decode().strip()
            (root / 'later.txt').write_text('second feature commit\n')
            run('add', '.'); run('commit', '-m', 'test: second feature change')
            head = run('rev-parse', 'HEAD').decode().strip()
            original = d.execute
            with patch.object(d, 'ROOT', root), patch.object(d, 'execute', side_effect=lambda args, **kw: original(args, cwd=root, **kw)):
                manifest = d.make_manifest(intermediate, [])
                # Final-tree equality by itself cannot reveal the missing earlier review.
                self.assertEqual(d.tree_entries(head), {p: {'blob': r['blob'], 'mode': r['mode']} for p, r in manifest['files'].items()})
                self.assertEqual(manifest['changed'], ['later.txt'])
            self.manifest = manifest
            for report in [self.code, self.security, self.local]:
                report.update(base=intermediate, digest=manifest['digest'])
            self.sha = head
            self.remote.update(base_sha=base, current_base_sha=base, head_sha=head, candidate_digest=manifest['digest'])
            for check in self.remote['checks']:
                check['head_sha'] = head
            with self.assertRaisesRegex(RuntimeError, 'earlier feature commits'):
                self.decide()

    def test_check_missing_skipped_failed_duplicate_or_wrong_provenance_blocks(self):
        baseline = copy.deepcopy(self.remote['checks'])
        alternatives = [baseline[:1], baseline + [baseline[0]]]
        for changes in [{'conclusion': 'SKIPPED'}, {'conclusion': 'FAILURE'}, {'status': 'IN_PROGRESS'},
                        {'head_sha': 'e' * 40}, {'app_slug': 'untrusted-bot'}, {'workflow_path': 'other.yml'}]:
            rows = copy.deepcopy(baseline); rows[0].update(changes); alternatives.append(rows)
        for rows in alternatives:
            self.remote['checks'] = rows
            with self.assertRaises(RuntimeError):
                self.decide()

    def test_high_risk_requires_distinct_fresh_security_reviewer(self):
        self.manifest['changed'] = ['src/storage.ts']
        self.security['reviewer'] = self.code['reviewer']
        with self.assertRaises(RuntimeError):
            self.decide()
        self.security['reviewer'] = 'author'
        with self.assertRaises(RuntimeError):
            self.decide()
        self.security['reviewer'] = 'subagent:second-independent-context'
        self.assertEqual(self.decide()['risk'], 'HIGH-RISK')

    def test_additional_effective_required_job_is_not_ignored(self):
        self.rules['required_checks'].append('Organization Policy')
        with self.assertRaises(RuntimeError):
            self.decide()

    def test_missing_or_stale_local_checks_block(self):
        baseline = copy.deepcopy(self.local)
        for changes in [{'complete': False}, {'digest': 'old'}, {'checks': self.local['checks'][:2]}, {'status': 'FAIL'}]:
            self.local = {**baseline, **changes}
            with self.assertRaises(RuntimeError):
                self.decide()

    def test_failed_or_missing_engineering_checks_and_contradictory_failure_block(self):
        baseline = copy.deepcopy(self.local['checks'])
        cases = [[x for x in baseline if x['name'] != 'engineering-config'],
                 [x for x in baseline if x['name'] != 'engineering-tests'],
                 [*baseline, {'name': 'another-mandatory-command', 'exit_code': 1}]]
        failed = copy.deepcopy(baseline); failed[-1]['exit_code'] = 1; cases.append(failed)
        for rows in cases:
            self.local['checks'] = rows
            with self.assertRaises(RuntimeError):
                self.decide()

    def test_empty_or_reduced_ci_profile_cannot_authorize(self):
        for required in [[], ['Secrets'], ['Secrets', 'Secrets']]:
            self.config['required_jobs'] = required
            self.rules['required_checks'] = required
            with self.assertRaises(RuntimeError):
                self.decide()


if __name__ == '__main__':
    unittest.main()
