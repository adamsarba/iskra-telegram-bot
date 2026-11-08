"""Offline regression checks for command authorization and read-only limit queries."""

import copy
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import listener


class ListenerTests(unittest.TestCase):
    def setUp(self):
        self.update = {'update_id': 10, 'message': {'date': 1000, 'text': '/status',
                       'chat': {'id': 123, 'type': 'private'},
                       'from': {'id': 123, 'is_bot': False}}}

    def accepts(self, update):
        return listener.authorized_status(update, 123, 'example_iskra_bot', 1000)

    def test_owner_and_addressed_command(self):
        for text, mode in [('/status', 'full'), ('/status@example_iskra_bot', 'full'),
                           ('/status short', 'short'), ('/status@example_iskra_bot short', 'short')]:
            self.update['message']['text'] = text
            self.assertEqual(self.accepts(self.update), mode)

    def test_rejects_other_senders_groups_and_bots(self):
        for field, key, value in [('from', 'id', 999), ('chat', 'id', 999),
                                  ('chat', 'type', 'group'), ('from', 'is_bot', True)]:
            update = copy.deepcopy(self.update)
            update['message'][field][key] = value
            self.assertFalse(self.accepts(update))

    def test_rejects_forwarded_stale_and_arbitrary_commands(self):
        for key, value in [('forward_origin', {'type': 'user'}), ('via_bot', {'id': 456}),
                           ('date', 800), ('date', 1010), ('text', '/status extra'), ('text', '/status short extra'),
                           ('text', '/status@other_bot'), ('text', '$(touch /tmp/injected)')]:
            update = copy.deepcopy(self.update)
            update['message'][key] = value
            self.assertFalse(self.accepts(update))
        self.assertFalse(self.accepts({'edited_message': self.update['message']}))

    def test_secrets_are_only_on_curl_stdin(self):
        with patch('listener.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{"ok": true}\n200'
            listener.request('https://example.com/botFAKE_TOKEN/getUpdates',
                             headers=['Authorization: Bearer FAKE_SECRET'])
            args, kwargs = run.call_args
            self.assertNotIn('FAKE_TOKEN', repr(args))
            self.assertNotIn('FAKE_SECRET', repr(args))
            self.assertIn('FAKE_SECRET', kwargs['input'])
            self.assertIn('--max-time', args[0])

    def test_error_body_does_not_escape(self):
        with patch('listener.subprocess.run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = 'sensitive-response\n401'
            with self.assertRaisesRegex(listener.Unavailable, '^HTTP 401$'):
                listener.request('https://example.com')

    def test_private_atomic_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            cursor = Path(directory) / 'offset.json'
            listener.save_json(cursor, 11)
            self.assertEqual(json.loads(cursor.read_text()), 11)
            self.assertEqual(cursor.stat().st_mode & 0o777, 0o600)

    def test_format_and_partial_provider_failure(self):
        self.assertIn('65% left', listener.window_text(300, 35, 4600, 1000))
        self.assertIn('\n   Reset in 1h 0m\n', listener.window_text(300, 35, 4600, 1000))
        self.assertNotIn('used', listener.window_text(300, 35, 4600, 1000))
        with patch('listener.claude_configured', return_value=True), \
             patch('listener.codex_limits', return_value=[(300, 35, None)]), \
             patch('listener.claude_limits', side_effect=listener.Unavailable('HTTP 401')):
            text = listener.status_text('/fake/codex')
            self.assertIn('65% left', text)
            self.assertIn('Claude\nData unavailable\nHTTP 401', text)
            self.assertIn('Updated ', text)
            self.assertIn(' · ' + listener.TIMEZONE_LABEL, text)

    def test_short_status_one_line_per_provider(self):
        with patch('listener.claude_configured', return_value=True), \
             patch('listener.claude_limits', return_value=[(300, 12, 4600), (10080, 46.4, 9000)]), \
             patch('listener.codex_limits', side_effect=listener.Unavailable('HTTP 401')):
            text = listener.status_text('/fake/codex', short=True)
        self.assertEqual(text, 'Claude 5h 88% · 7d 54%\nCodex n/a')

    def test_single_provider(self):
        with patch('listener.claude_configured', return_value=False), \
             patch('listener.codex_limits', return_value=[(300, 35, None)]):
            text = listener.status_text('/fake/codex')
            self.assertIn('Codex\n', text)
            self.assertNotIn('Claude', text)
        with patch('listener.claude_configured', return_value=True), \
             patch('listener.claude_limits', return_value=[(300, 35, None)]):
            text = listener.status_text(None)
            self.assertIn('Claude\n', text)
            self.assertNotIn('Codex', text)

    def test_compact_dates_width_and_midnight(self):
        now = dt.datetime(2026, 11, 8, 23, 0, tzinfo=listener.TIMEZONE).timestamp()
        reset = dt.datetime(2026, 11, 9, 8, 0, tzinfo=listener.TIMEZONE).timestamp()
        self.assertIn('Mon tomorrow 8AM', listener.window_text(300, 87, reset, now))
        self.assertIn('Mon 09.11 8AM', listener.window_text(10080, 60, reset, now))
        self.assertIn('Sun today 11PM', listener.window_text(300, 87, now, now - 60))
        for used in (0, 13, 40, 99, 100):
            for window in (300, 10080):
                lines = listener.window_text(window, used, reset, now).splitlines()
                self.assertLessEqual(max(map(len, lines)), 27)

    def test_monospace_payload_escapes_html(self):
        fields = listener.status_fields(123, 'Codex <x> & data')
        self.assertEqual(fields['parse_mode'], 'HTML')
        self.assertEqual(fields['text'], '<pre>Codex &lt;x&gt; &amp; data</pre>')

    def test_duplicate_and_unauthorized_updates_cannot_trigger_status(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / 'chat_id').write_text('123')
            listener.save_json(config / 'offset.json', 10)
            stranger = copy.deepcopy(self.update)
            stranger['update_id'] = 11
            stranger['message']['from']['id'] = 999
            calls = []

            def telegram(method, fields=None):
                calls.append((method, fields))
                if method == 'getMe':
                    return {'username': 'example_iskra_bot'}
                if method == 'getChat':
                    return {'type': 'private', 'id': 123}
                if method == 'getUpdates':
                    polls = sum(item[0] == 'getUpdates' for item in calls)
                    if polls == 1:
                        return [self.update, self.update, stranger]
                    raise KeyboardInterrupt
                return {}

            with patch('listener.CONFIG', config), patch('listener.telegram', side_effect=telegram), \
                 patch('listener.status_text', return_value='status') as status, \
                 patch('listener.time.time', return_value=1000), patch('sys.stdout', io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    listener.listen('/fake/codex')
                status.assert_called_once()
            self.assertEqual(sum(method == 'sendMessage' for method, _ in calls), 1)
            self.assertEqual(json.loads((config / 'offset.json').read_text()), 12)


if __name__ == '__main__':
    unittest.main()
