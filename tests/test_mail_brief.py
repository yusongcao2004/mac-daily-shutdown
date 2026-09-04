import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from mail_brief import collect_mail, normalize, previous_brief

def sample():
    return {'sources': [dict(source=s, account=s+'@example.test', status='ok',
        coverage='Queried requested window.', tool_evidence=['get_profile', 'search: 0'])
        for s in ('gmail', 'outlook', 'calendar')], 'important_mail': '无新增重要邮件',
        'upcoming_schedule': '未来24小时无日程', 'attention_items': [], 'dedup_state': 'empty'}

class MailTests(unittest.TestCase):
    def test_account_mismatch_cannot_be_complete(self):
        data = normalize(sample(), {'gmail': 'personal@example.test'})
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(data['sources'][0]['status'], 'partial')
        self.assertIn('预期账号不同', data['sources'][0]['coverage'])

    def test_missing_coverage_or_evidence_is_not_success(self):
        data = sample(); data['sources'].pop()
        with self.assertRaises(ValueError): normalize(data, {})
        data = sample(); data['sources'][0]['tool_evidence'] = []
        self.assertEqual(normalize(data, {})['status'], 'partial')

    def test_failed_read_keeps_explicit_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)/'current'; run.mkdir()
            def failed(*args, **kwargs): raise RuntimeError('Connector unavailable')
            packet = {'window_start': '2026-01-01T12:00:00+01:00',
                      'window_end': '2026-01-02T12:00:00+01:00'}
            data = collect_mail(run, packet, failed, 'fake-codex')
            self.assertEqual(data['status'], 'partial')
            self.assertIn('未能完成', data['important_mail'])
            self.assertTrue(all(s['status'] == 'unavailable' for s in data['sources']))

    def test_unsubmitted_preview_is_not_dedup_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root/'previous'; old.mkdir()
            (old/'mail-brief.json').write_text(json.dumps(sample()))
            current = root/'current'; current.mkdir()
            self.assertIsNone(previous_brief(current))
            (old/'recipient-confirmation.json').write_text('{"text_received":true}')
            self.assertEqual(previous_brief(current), old/'mail-brief.json')

if __name__ == '__main__':
    unittest.main()
