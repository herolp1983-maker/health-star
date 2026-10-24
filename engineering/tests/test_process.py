"""Execute the process gate against real failing and missing processes, without Android."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('pwsh'), 'Windows process gate requires PowerShell 7')
class ProcessGateTests(unittest.TestCase):
    def run_gate(self, file, arguments):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'fixture.ps1'
            helper = str(ROOT / 'engineering/process-check.ps1').replace("'", "''")
            file = str(file).replace("'", "''")
            args = ','.join("'" + a.replace("'", "''") + "'" for a in arguments)
            script.write_text(f". '{helper}'\nInvoke-VerifiedProcess -File '{file}' -Arguments @({args}) -Log '{directory}/process.log' | ConvertTo-Json\n")
            result = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], capture_output=True, text=True, encoding='utf-8', timeout=30, check=True)
            return json.loads(result.stdout.lstrip('\ufeff'))

    def test_missing_executable_is_never_success(self):
        result = self.run_gate('nonexistent-engineering-process-fixture', [])
        self.assertFalse(result['started'])
        self.assertNotEqual(result['exit_code'], 0)

    def test_native_failure_and_stderr_keep_actual_exit_status(self):
        result = self.run_gate(shutil.which('pwsh'), ['-NoProfile', '-Command', '[Console]::Error.WriteLine("fixture warning"); exit 7'])
        self.assertTrue(result['started'])
        self.assertEqual(result['exit_code'], 7)

    def test_success_with_stderr_is_executed_and_successful(self):
        result = self.run_gate(shutil.which('pwsh'), ['-NoProfile', '-Command', '[Console]::Error.WriteLine("fixture warning"); exit 0'])
        self.assertTrue(result['started'])
        self.assertEqual(result['exit_code'], 0)

    def test_release_without_signing_identity_fails_before_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'scripts').mkdir()
            script = root / 'scripts/build-android.ps1'
            shutil.copyfile(ROOT / 'hero-health-android/scripts/build-android.ps1', script)
            result = subprocess.run(['pwsh', '-NoProfile', '-File', str(script)], capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Original signing.properties is required', result.stderr)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['scripts'])
