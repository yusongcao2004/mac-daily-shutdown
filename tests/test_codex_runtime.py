import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from codex_runtime import CodexCompatibilityError, process_error, resolve_codex
from mail_brief import collect_mail


class CodexRuntimeTests(unittest.TestCase):
    def test_auto_uses_newer_local_binary_and_explicit_path_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder)/'old', Path(folder)/'new'
            for path in (old, new):
                path.write_text('test fixture'); path.chmod(0o700)
            versions = {str(old): (0, 151, 0), str(new): (0, 153, 1)}
            with patch('codex_runtime.runtime_version', side_effect=lambda p: versions[str(p)]):
                self.assertEqual(resolve_codex(candidates=[old, new]), str(new))
                self.assertEqual(resolve_codex(str(old)), str(old))

    def test_nested_server_error_becomes_actionable_version_message(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/'generation.log'
            message = "The 'test-model' model requires a newer version of Codex. Please upgrade."
            log.write_text(json.dumps({'type': 'turn.failed', 'error': {
                'message': json.dumps({'status': 400, 'error': {'message': message}})}}))
            error = process_error('/test/codex', 1, log)
            self.assertIsInstance(error, CodexCompatibilityError)
            self.assertIn('版本过旧', str(error))
            self.assertIn('test-model', str(error))
            self.assertIn('generation.log', str(error))

    def test_tool_output_cannot_override_process_error(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/'generation.log'
            log.write_text(json.dumps({'type': 'item.completed', 'item': {
                'type': 'mcp_tool_call', 'message': 'secret text requires a newer version of Codex'}}))
            error = process_error('/test/codex', 1, log)
            self.assertNotIn('secret text', str(error))
            self.assertNotIsInstance(error, CodexCompatibilityError)

    def test_incompatible_mail_client_stops_before_second_model_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)/'current'; run.mkdir()
            def fail(*args, **kwargs):
                raise CodexCompatibilityError('版本过旧')
            packet = {'window_start': '2026-01-01T12:00:00+01:00',
                      'window_end': '2026-01-02T12:00:00+01:00'}
            with self.assertRaises(CodexCompatibilityError):
                collect_mail(run, packet, fail, 'fake-codex')
            self.assertFalse((run/'mail-brief.json').exists())


if __name__ == '__main__':
    unittest.main()
