"""Behavioral gate tests using isolated Git repos, not the user's worktree."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delivery as d


class GateTests(unittest.TestCase):
    def test_explicit_third_repair_batch_is_bound_to_one_delivery(self):
        ledger = {'id': 'delivery-1', 'fix_rounds': 2, 'fixes': [{}, {}]}
        with self.assertRaises(RuntimeError):
            d.reserve_fix(ledger, 'CI repair')
        ledger['repair_exception'] = {'delivery_id': 'delivery-1', 'max_rounds': 3,
                                      'approved_by': 'user', 'scope': 'this delivery only',
                                      'approval': 'Explicit approval for third batch', 'approved_utc': 1}
        self.assertEqual(d.reserve_fix(ledger, 'CI repair')['fix_rounds'], 3)
        with self.assertRaises(RuntimeError):
            d.reserve_fix(ledger, 'another repair')
        ledger['repair_exception']['delivery_id'] = 'different-delivery'
        with self.assertRaises(RuntimeError):
            d.repair_limit(ledger)

    def report(self):
        return {'status': 'PASS', 'base': 'base', 'digest': 'digest', 'complete': True,
                'reviewer': 'subagent:fresh-session', 'coverage': ['all changed paths, behavior and failure boundaries'], 'findings': []}

    def test_missing_pending_skipped_cancelled_and_duplicate_jobs_never_pass(self):
        for rows in [[], [{'name': 'Build', 'status': 'IN_PROGRESS'}],
                     [{'name': 'Build', 'status': 'COMPLETED', 'conclusion': 'SKIPPED'}],
                     [{'name': 'Build', 'status': 'COMPLETED', 'conclusion': 'CANCELLED'}],
                     [{'name': 'Build', 'status': 'COMPLETED', 'conclusion': 'NEUTRAL'}],
                     [{'name': 'Other', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'}],
                     [{'name': 'Build', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'}] * 2]:
            self.assertNotEqual(d.classify_checks(rows, ['Build']), 'PASS')

    def test_all_required_jobs_must_succeed(self):
        rows = [{'name': name, 'status': 'COMPLETED', 'conclusion': 'SUCCESS'} for name in ['Build', 'Security']]
        self.assertEqual(d.classify_checks(rows, ['Build', 'Security']), 'PASS')
        rows[1]['conclusion'] = 'FAILURE'
        self.assertEqual(d.classify_checks(rows, ['Build', 'Security']), 'FAIL')

    def test_incomplete_stale_self_review_and_high_findings_block(self):
        manifest = {'base': 'base', 'digest': 'digest'}
        variants = [{'complete': False}, {'digest': 'old'}, {'reviewer': 'author'}, {'coverage': []}, {'status': 'FAIL'},
                    {'findings': [{'severity': 'High', 'path': 'a.java', 'line': 1, 'impact': 'data disclosure', 'fix': 'check access'}]},
                    {'findings': [{'severity': 'nonsense', 'path': 'a', 'line': 1, 'impact': 'x', 'fix': 'x'}]}]
        for changes in variants:
            report = self.report(); report.update(changes)
            with self.assertRaises(RuntimeError):
                d.validate_review(report, manifest, 'code-review')
        d.validate_review(self.report(), manifest, 'code-review')

    def test_medium_findings_remain_nonblocking(self):
        report = self.report()
        report['findings'] = [{'severity': 'Medium', 'path': 'a.java', 'line': 2, 'impact': 'maintainability', 'fix': 'simplify'}]
        d.validate_review(report, {'base': 'base', 'digest': 'digest'}, 'code-review')

    def test_shared_budget_survives_serialization_and_crash_reservations(self):
        ledger = {'fix_rounds': 0, 'fixes': []}
        for count in [1, 2]:
            ledger = d.reserve_fix(json.loads(json.dumps(ledger)), 'aggregated local or CI findings')
            self.assertEqual(ledger['fix_rounds'], count)
        with self.assertRaises(RuntimeError):
            d.reserve_fix(json.loads(json.dumps(ledger)), 'third attempt after push')

    def test_risk_detects_renamed_old_path_and_sensitive_sources(self):
        paths = ['old/auth/login.kt', 'docs/old-login.md', 'app/AndroidManifest.xml', 'src/storage.ts', 'src/model.ts', '.github/workflows/ci.yml', 'app/src/HealthVault.java']
        flagged = d.sensitive(paths)
        for name in ['old/auth/login.kt', 'app/AndroidManifest.xml', 'src/storage.ts', '.github/workflows/ci.yml', 'app/src/HealthVault.java']:
            self.assertIn(name, flagged)
        self.assertIn('src/model.ts', flagged)
        self.assertEqual(d.sensitive(['hero-health-android/public/brand/hero-health-logo.png']), [])

    def test_review_patch_only_adjudicates_exact_added_fixture(self):
        fixtures = json.loads((d.ROOT / 'engineering/secret-fixtures.json').read_text(encoding='utf-8'))
        fixture = fixtures[0]
        path = fixture['path']
        lines = (d.ROOT / path).read_text(encoding='utf-8').splitlines()
        literal = next(line for line in lines if any(
            hit['fingerprint'] == fixture['fingerprint'] for hit in d.secret_findings(line, path)))
        header = f'diff --git a/{path} b/{path}\n@@ -0,0 +1 @@\n'
        added = d.patch_secret_findings(header + '+' + literal + '\n', fixtures)
        self.assertEqual(added[0]['path'], path)
        self.assertEqual(added[0]['fingerprint'], fixture['fingerprint'])
        removed = d.patch_secret_findings(header + '-' + literal + '\n', fixtures)
        self.assertEqual(removed[0]['path'], '.engineering/candidate/change.patch')
        changed = d.patch_secret_findings(header + '+' + literal + 'altered\n', fixtures)
        self.assertEqual(changed[0]['path'], '.engineering/candidate/change.patch')

    def test_secrets_are_redacted_and_artifacts_forbidden(self):
        token = 'gh' + 'p_' + 'A' * 36
        findings = d.secret_findings('key="' + token + '"', 'source.txt')
        self.assertTrue(findings)
        self.assertNotIn(token, json.dumps(findings))
        self.assertEqual(d.forbidden_paths(['app/build/a.apk', '.keys/key.jks', 'signing.properties', 'src/a.java']), ['app/build/a.apk', '.keys/key.jks', 'signing.properties'])

    def test_fixture_adjudication_binds_exact_content_and_never_real_token_rules(self):
        path = 'project/scripts/test-domain.mjs'
        hits = d.secret_findings('apiKey:' + repr('synthetic-fixture-value-only'), path)
        entry = {k: hits[0][k] for k in ['path', 'rule', 'fingerprint']}
        entry['reason'] = 'A verified deliberately synthetic fixture tests key exclusion'
        remaining, approved = d.adjudicate_fixtures(hits, [entry])
        self.assertEqual(remaining, [])
        self.assertEqual(len(approved), 1)
        changed = d.secret_findings('apiKey:' + repr('changed-unknown-value-needs-review'), path)
        self.assertTrue(d.adjudicate_fixtures(changed, [entry])[0])
        with self.assertRaises(RuntimeError):
            d.adjudicate_fixtures(hits, [{**entry, 'rule': 'github-token'}])


class RepositoryTests(unittest.TestCase):
    def test_advancing_target_base_preserves_identity_and_exhausted_repair_budget(self):
        with tempfile.TemporaryDirectory(prefix='engineering-ledger-fixture-') as temp:
            root = Path(temp)
            def run(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            run('init', '-b', 'main'); run('config', 'user.name', 'Fixture'); run('config', 'user.email', 'fixture@example.invalid')
            (root / '.gitignore').write_text('.engineering/\n')
            (root / 'engineering').mkdir()
            (root / 'engineering/project.json').write_text(json.dumps({'protected_branches': ['main', 'master'], 'default_branch': 'main'}))
            (root / 'README.md').write_text('base\n'); run('add', '.'); run('commit', '-m', 'test: base')
            base = run('rev-parse', 'HEAD').decode().strip()
            run('switch', '-c', 'codex/feature')
            (root / 'feature.txt').write_text('feature\n'); run('add', '.'); run('commit', '-m', 'test: feature')
            original = d.execute
            evidence = root / '.engineering'
            with patch.object(d, 'ROOT', root), patch.object(d, 'EVIDENCE', evidence), \
                 patch.object(d, 'execute', side_effect=lambda args, **kw: original(args, cwd=root, **kw)), redirect_stdout(io.StringIO()):
                d.ledger(SimpleNamespace(command='start', base=base))
                _branch, path = d.ledger_path(); identity = d.read(path)['id']
                for number in [1, 2]:
                    d.ledger(SimpleNamespace(command='fix', reason=f'fixture repair batch {number}'))
                run('switch', 'main')
                (root / 'base-update.txt').write_text('new main\n'); run('add', '.'); run('commit', '-m', 'test: main advanced')
                target = run('rev-parse', 'HEAD').decode().strip()
                run('update-ref', 'refs/remotes/origin/main', target)
                run('switch', 'codex/feature'); run('merge', '--no-edit', 'main')
                d.ledger(SimpleNamespace(command='advance-base', base=target, reason='fetched main advanced'))
                changed = d.read(path)
                self.assertEqual((changed['id'], changed['fix_rounds'], changed['base']), (identity, 2, target))
                self.assertEqual(len(changed['base_changes']), 1)
                with self.assertRaises(RuntimeError):
                    d.ledger(SimpleNamespace(command='fix', reason='not a fresh budget after rebasing'))
                with self.assertRaisesRegex(RuntimeError, 'fetched default branch'):
                    d.ledger(SimpleNamespace(command='advance-base', base='HEAD', reason='feature is not target'))

    def test_review_inputs_are_bound_and_removed_secrets_block_sharing(self):
        with tempfile.TemporaryDirectory(prefix='engineering-review-fixture-') as temp:
            root = Path(temp)
            def run(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            run('init', '-b', 'codex/test'); run('config', 'user.name', 'Fixture'); run('config', 'user.email', 'fixture@example.invalid')
            (root / '.gitignore').write_text('.engineering/\n')
            secret = 'gh' + 'p_' + 'A' * 36
            (root / 'source.txt').write_text(secret + '\n')
            run('add', '.'); run('commit', '-m', 'test: synthetic old credential')
            base = run('rev-parse', 'HEAD').decode().strip()
            (root / 'source.txt').write_text('removed credential\n')
            (root / 'unrelated.txt').write_text('preserve unrelated work\n')
            evidence = root / '.engineering'; candidate = evidence / 'candidate'
            evidence.mkdir(); requirements = evidence / 'request.txt'; requirements.write_text('review removal\n')
            original = d.execute
            with patch.object(d, 'ROOT', root), patch.object(d, 'CANDIDATE', candidate), patch.object(d, 'EVIDENCE', evidence), \
                 patch.object(d, 'execute', side_effect=lambda args, **kw: original(args, cwd=root, **kw)), redirect_stdout(io.StringIO()):
                d.snapshot(SimpleNamespace(base=base, requirements=str(requirements), untracked_paths=None))
                # Fresh Windows snapshots must validate without CRLF/hash mismatches.
                manifest = d.current_manifest()
                self.assertNotIn('unrelated.txt', manifest['files'])
                with self.assertRaisesRegex(RuntimeError, 'Potential secrets'):
                    d.security(SimpleNamespace(workspace=False))
                static = d.read(evidence / 'security-static.json')
                self.assertTrue(any(x['path'].endswith('change.patch') for x in static['secret_findings_redacted']))
                self.assertNotIn(secret, json.dumps(static))
                (candidate / 'change.patch').write_text('truncated\n')
                with self.assertRaisesRegex(RuntimeError, 'Review patch changed'):
                    d.current_manifest()
                # A tracked binary signing key is rejected before a review export.
                (root / 'signing.jks').write_bytes(b'\0synthetic-only')
                run('add', 'signing.jks')
                with self.assertRaisesRegex(RuntimeError, 'Forbidden candidate'):
                    d.snapshot(SimpleNamespace(base=base, requirements=str(requirements), untracked_paths=None))

    def test_snapshot_catches_unstaged_untracked_deleted_and_stale_requirements(self):
        with tempfile.TemporaryDirectory(prefix='engineering-git-test-') as temp:
            root = Path(temp)
            def run(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            run('init', '-b', 'codex/test'); run('config', 'user.name', 'Fixture'); run('config', 'user.email', 'fixture@example.invalid')
            (root / '.gitignore').write_text('.engineering/\n')
            (root / 'source.txt').write_text('before\n')
            (root / 'deleted.txt').write_text('remove\n')
            run('add', '.'); run('commit', '-m', 'test: baseline')
            base = run('rev-parse', 'HEAD').decode().strip()
            (root / 'source.txt').write_text('after\n')
            (root / 'deleted.txt').unlink()
            (root / 'new.txt').write_text('untracked\n')
            candidate = root / '.engineering/candidate'
            with patch.object(d, 'ROOT', root), patch.object(d, 'CANDIDATE', candidate):
                # execute's default cwd is fixed at import; replace it explicitly for the fixture.
                original = d.execute
                with patch.object(d, 'execute', side_effect=lambda args, **kw: original(args, cwd=root, **kw)):
                    manifest = d.make_manifest(base)
                    self.assertEqual(manifest['changed'], ['deleted.txt', 'new.txt', 'source.txt'])
                    (root / 'new.txt').write_text('changed again\n')
                    self.assertNotEqual(manifest['digest'], d.make_manifest(base)['digest'])


if __name__ == '__main__':
    unittest.main()
