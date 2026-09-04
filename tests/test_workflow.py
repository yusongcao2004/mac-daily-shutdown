import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class WorkflowTests(unittest.TestCase):
    def test_unapproved_run_cannot_collect_or_send(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)/'private-state'
            result = subprocess.run([sys.executable, str(ROOT/'src/runner.py'), '--mode', 'send'],
                env={**os.environ, 'DAILY_SHUTDOWN_HOME': str(home)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('待用户明确授权', result.stdout)
            self.assertFalse((home/'runs').exists())

    def test_scanner_obeys_scope_exclusions_and_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            docs = base/'docs'; docs.mkdir()
            home = docs/'private-state'; home.mkdir()
            (docs/'note.txt').write_text('first')
            (docs/'node_modules').mkdir()
            (docs/'node_modules/ignored.txt').write_text('dependency')
            outside = base/'outside.txt'; outside.write_text('outside scope')
            (docs/'link.txt').symlink_to(outside)
            (home/'config.json').write_text(json.dumps({'scan_roots': [str(docs)]}))
            def scan():
                result = subprocess.run([sys.executable, str(ROOT/'src/daily_scan.py')],
                    env={**os.environ, 'DAILY_SHUTDOWN_HOME': str(home)},
                    capture_output=True, text=True, check=True)
                return json.loads(Path(json.loads(result.stdout)['scan']).read_text())
            first = scan()
            self.assertEqual(first['file_count'], 1)
            self.assertIsNone(first['baseline_time'])
            self.assertEqual(first['recent'][0]['path'], str(docs/'note.txt'))
            (docs/'note.txt').unlink()
            second = scan()
            self.assertIsNotNone(second['baseline_time'])
            self.assertEqual(second['missing_since_baseline_not_confirmed_deleted'], [str(docs/'note.txt')])

if __name__ == '__main__':
    unittest.main()
