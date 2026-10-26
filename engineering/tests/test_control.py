import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control as c


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {'base': 'base', 'digest': 'candidate', 'changed': ['docs/readme.md']}
        self.ledger = {'id': 'delivery', 'base': 'base'}
        self.config = {'process_control': {'max_wall_minutes': 120, 'compatibility_paths': ['adapter.py']}}
        self.preflight = {'base': 'base', 'digest': 'candidate', 'complete': True, 'status': 'PASS',
                          'checks': [{'name': n, 'exit_code': 0, 'evidence': n + '.log'} for n in
                                     ['baseline', 'engineering-config', 'engineering-tests', 'tools']]}
        self.plan = c.initialize(self.manifest, self.ledger, self.preflight, self.config, 100)
        self.plan['candidates']['candidate'] = {'preflight': self.preflight, 'phases': {}}

    def test_same_candidate_cannot_launch_same_costly_phase_twice(self):
        for phase in c.PHASES:
            c.reserve(self.plan, self.manifest, self.ledger, self.config, phase, 101)
            with self.assertRaisesRegex(RuntimeError, 'already reserved'):
                c.reserve(self.plan, self.manifest, self.ledger, self.config, phase, 102)

    def test_changed_content_cannot_use_previous_preflight(self):
        changed = {**self.manifest, 'digest': 'new'}
        with self.assertRaisesRegex(RuntimeError, 'Bind passing preflight'):
            c.reserve(self.plan, changed, self.ledger, self.config, 'code-review', 102)
        with self.assertRaisesRegex(RuntimeError, 'Stale preflight'):
            c.validate_preflight(self.preflight, changed, False)

    def test_adapter_change_requires_real_consumer_compatibility_evidence(self):
        changed = {**self.manifest, 'changed': ['adapter.py']}
        with self.assertRaisesRegex(RuntimeError, 'consumer probe'):
            c.initialize(changed, self.ledger, self.preflight, self.config, 100)
        self.preflight['checks'].append({'name': 'consumer-compatibility', 'exit_code': 0, 'evidence': 'actual-scanner.log'})
        c.initialize(changed, self.ledger, self.preflight, self.config, 100)

    def test_failed_missing_duplicate_or_unsubstantiated_preflight_blocks(self):
        for mutation in ['failed', 'missing', 'duplicate', 'evidence']:
            report = copy.deepcopy(self.preflight)
            if mutation == 'failed': report['checks'][0]['exit_code'] = 1
            if mutation == 'missing': report['checks'].pop()
            if mutation == 'duplicate': report['checks'].append(report['checks'][0])
            if mutation == 'evidence': report['checks'][0]['evidence'] = ''
            with self.assertRaises(RuntimeError): c.validate_preflight(report, self.manifest, False)

    def test_deadline_and_profile_are_not_reset_by_new_candidate(self):
        for manifest in [self.manifest, {**self.manifest, 'digest': 'new'}]:
            with self.assertRaisesRegex(RuntimeError, 'wall-time'):
                c.verify(self.plan, manifest, self.ledger, self.config, 7300)
        with self.assertRaisesRegex(RuntimeError, 'profile changed'):
            c.verify(self.plan, self.manifest, self.ledger, {'process_control': {}}, 101)

    def test_repeated_fault_requires_new_strategy_and_probe_for_each_recurrence(self):
        self.plan['failures'] = [{'fingerprint': 'download', 'cause': 'read timeout'}] * 2
        with self.assertRaisesRegex(RuntimeError, 'changed strategy'):
            c.reserve(self.plan, self.manifest, self.ledger, self.config, 'code-review', 101)
        self.plan['resolutions']['download'] = {'failure_count': 2, 'base': 'base', 'digest': 'candidate'}
        c.reserve(self.plan, self.manifest, self.ledger, self.config, 'code-review', 102)
        self.plan['failures'].append({'fingerprint': 'download'})
        with self.assertRaisesRegex(RuntimeError, 'changed strategy'):
            c.verify(self.plan, self.manifest, self.ledger, self.config, 103)

    def test_concurrent_control_writer_cannot_duplicate_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'control.lock'
            with c.locked(path):
                with self.assertRaisesRegex(RuntimeError, 'locked'):
                    with c.locked(path): self.fail('Second writer acquired lock')
            self.assertFalse(path.exists())

    def test_gate_requires_each_current_candidate_reservation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(c.time, 'time', return_value=101):
            root = Path(folder); (root / '.engineering').mkdir()
            target = c.state_path(root, self.ledger); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self.plan))
            with self.assertRaisesRegex(RuntimeError, 'reservations missing'):
                c.verify_gate(root, self.manifest, self.ledger, self.config)
            for phase in ['code-review', 'security-review', 'local-checks']:
                c.reserve(self.plan, self.manifest, self.ledger, self.config, phase, 101)
            target.write_text(json.dumps(self.plan))
            c.verify_gate(root, self.manifest, self.ledger, self.config)
            with self.assertRaisesRegex(RuntimeError, 'reservations missing'):
                c.verify_gate(root, self.manifest, self.ledger, self.config, include_remote=True)
            c.reserve(self.plan, self.manifest, self.ledger, self.config, 'remote-review-request', 102)
            target.write_text(json.dumps(self.plan))
            c.verify_gate(root, self.manifest, self.ledger, self.config, include_remote=True)

    def test_new_delivery_keeps_separate_history_and_cannot_reset_existing_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_path = c.state_path(root, self.ledger); old_path.parent.mkdir(parents=True)
            old_path.write_text(json.dumps(self.plan))
            second = {**self.ledger, 'id': 'next-delivery'}
            new_path = c.state_path(root, second)
            new_plan = c.initialize(self.manifest, second, self.preflight, self.config, 200)
            new_path.write_text(json.dumps(new_plan))
            self.assertNotEqual(old_path, new_path)
            self.assertEqual(json.loads(old_path.read_text()), self.plan)
            c.verify(new_plan, self.manifest, second, self.config, 201)
            with self.assertRaisesRegex(RuntimeError, 'wall-time'):
                c.verify(json.loads(old_path.read_text()), self.manifest, self.ledger, self.config, 7300)

    def test_recorded_base_advance_preserves_history_and_requires_fresh_candidate(self):
        c.reserve(self.plan, self.manifest, self.ledger, self.config, 'code-review', 101)
        original = copy.deepcopy(self.plan)
        advanced = {**self.ledger, 'base': 'next-base', 'base_changes': [
            {'previous_base': 'base', 'new_base': 'next-base', 'reason': 'main advanced'}]}
        c.synchronize_base(self.plan, advanced, lambda old, new: (old, new) == ('base', 'next-base'))
        manifest = {**self.manifest, 'base': 'next-base', 'digest': 'next-candidate'}
        with self.assertRaisesRegex(RuntimeError, 'Bind passing preflight'):
            c.reserve(self.plan, manifest, advanced, self.config, 'code-review', 102)
        report = {**self.preflight, 'base': 'next-base', 'digest': 'next-candidate'}
        c.validate_preflight(report, manifest, False)
        self.plan['candidates']['next-candidate'] = {'preflight': report, 'phases': {}}
        for phase in c.PHASES:
            c.reserve(self.plan, manifest, advanced, self.config, phase, 103)
        self.assertEqual(self.plan['deadline'], original['deadline'])
        self.assertEqual(self.plan['candidates']['candidate'], original['candidates']['candidate'])
        for bad in [self.ledger, {**advanced, 'id': 'other'}, {**advanced, 'base_changes': []}]:
            with self.assertRaises(RuntimeError):
                c.synchronize_base(copy.deepcopy(original), {**bad, 'base': 'next-base'}, lambda a, b: True)
        with self.assertRaises(RuntimeError):
            c.synchronize_base(copy.deepcopy(original), advanced, lambda a, b: False)

    def test_repeated_fault_probe_cannot_be_reused_after_candidate_or_base_change(self):
        self.plan['failures'] = [{'fingerprint': 'download'}] * 2
        self.plan['resolutions']['download'] = {'failure_count': 2, 'base': 'base', 'digest': 'candidate'}
        c.verify(self.plan, self.manifest, self.ledger, self.config, 101)
        for changed in [{**self.manifest, 'digest': 'new'}, {**self.manifest, 'base': 'new-base'}]:
            with self.assertRaises(RuntimeError):
                c.verify(self.plan, changed, self.ledger, self.config, 102)
