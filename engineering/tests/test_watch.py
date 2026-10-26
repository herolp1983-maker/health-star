from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import watch as w


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.head = 'a' * 40
        self.snapshot = {'source': 'github-api', 'head_sha': self.head, 'fetched_at': 100,
                         'checks': [{'name': n, 'head_sha': self.head, 'app_slug': 'github-actions',
                                     'status': 'completed', 'conclusion': 'success'} for n in ['Build', 'Security']]}

    def state(self, previous=None, now=101):
        return w.observe(previous, self.snapshot, ['Build', 'Security'], self.head, 200, now)

    def test_success_is_notification_only_and_never_merge_authority(self):
        result = self.state(); self.assertEqual(result['status'], 'SUCCESS')
        self.assertTrue(result['notify']); self.assertFalse(result['merge_authorized'])
        self.assertFalse(self.state(result)['notify'])

    def test_unchanged_pending_is_quiet_and_does_not_reset_deadline(self):
        self.snapshot['checks'][0].update(status='in_progress', conclusion=None)
        result = self.state(); self.assertEqual(result['status'], 'PENDING'); self.assertFalse(result['notify'])
        self.assertFalse(self.state(result)['notify']); self.assertEqual(self.state(result)['deadline'], 200)
        with self.assertRaises(RuntimeError):
            w.observe(result, self.snapshot, ['Build'], self.head, 300, 102)

    def test_missing_checks_are_pending_not_success(self):
        self.snapshot['checks'] = []
        self.assertEqual(self.state()['status'], 'PENDING')
        self.assertEqual(w.evaluate(self.snapshot, [], self.head, 200, 101), 'BLOCKED')

    def test_failed_skipped_neutral_cancelled_jobs_never_pass(self):
        for conclusion in ['failure', 'skipped', 'neutral', 'cancelled', None]:
            self.snapshot['checks'][0]['conclusion'] = conclusion
            self.assertEqual(self.state()['status'], 'FAILURE')

    def test_stale_future_wrong_head_and_wrong_source_block(self):
        for field, value in [('fetched_at', -999), ('fetched_at', 102), ('head_sha', 'b' * 40), ('source', 'guess')]:
            previous = self.snapshot[field]; self.snapshot[field] = value
            self.assertEqual(self.state()['status'], 'BLOCKED'); self.snapshot[field] = previous
        self.snapshot['checks'][0]['app_slug'] = 'another-app'
        self.assertEqual(self.state()['status'], 'BLOCKED')

    def test_duplicate_jobs_and_unknown_states_block(self):
        self.snapshot['checks'].append(self.snapshot['checks'][0].copy())
        self.assertEqual(self.state()['status'], 'BLOCKED')
        self.snapshot['checks'].pop(); self.snapshot['checks'][0]['status'] = 'made-up'
        self.assertEqual(self.state()['status'], 'BLOCKED')

    def test_expiry_is_terminal_even_when_ci_is_successful(self):
        self.assertEqual(self.state(now=200)['status'], 'EXPIRED')

    def test_credentials_are_not_forwarded_to_redirects(self):
        self.assertIsNone(w.NoRedirect().redirect_request(None, None, 302, 'redirect', {}, 'https://other.invalid'))
