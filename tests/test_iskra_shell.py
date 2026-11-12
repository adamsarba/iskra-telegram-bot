"""Offline checks for iskra.sh token diagnostics and secret handling."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'iskra.sh'


class IskraShellTests(unittest.TestCase):
    def run_iskra(self, token_result, curl_response='{"ok": true, "result": [{"message": {"chat": {"id": 123, "type": "private"}}}]}'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / 'bin'
            config = root / '.config' / 'iskra'
            bin_dir.mkdir()
            config.mkdir(parents=True)
            security = bin_dir / 'security'
            security.write_text('#!/bin/bash\n' + token_result)
            curl = bin_dir / 'curl'
            curl.write_text('#!/bin/bash\ncat >/dev/null\nprintf %s ' + repr(curl_response) + '\n')
            security.chmod(0o755)
            curl.chmod(0o755)
            env = dict(os.environ, HOME=str(root), PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
            return subprocess.run(['bash', str(SCRIPT), 'setup'], env=env,
                                  capture_output=True, text=True)

    def test_setup_reads_valid_token_without_printing_secret(self):
        secret = '123456:FAKE_SECRET'
        result = self.run_iskra("printf '%s\\n' '" + secret + "'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_normal_send_never_reads_keychain_or_calls_curl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('security', 'curl'):
                stub = root / name
                stub.write_text('#!/bin/bash\ntouch "' + str(root / 'forbidden') + '"\nexit 99\n')
                stub.chmod(0o755)
            python = root / 'python3'
            python.write_text('#!/bin/bash\nexit 23\n')
            python.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'])
            for args in (['text'], ['--gif', 'https://example.com/a.gif', 'caption']):
                result = subprocess.run(['bash', str(SCRIPT)] + args, env=env, capture_output=True)
                self.assertEqual(result.returncode, 23)
            self.assertFalse((root / 'forbidden').exists())

    def test_keychain_read_failure_is_ambiguous_and_actionable(self):
        result = self.run_iskra('exit 44')
        message = result.stderr
        self.assertIn('may be missing', message)
        self.assertIn('denied access', message)
        self.assertIn('outside the sandbox', message)
        self.assertNotIn('Bot token missing from Keychain', message)

    def test_invalid_token_format_is_distinct(self):
        result = self.run_iskra("printf '%s\\n' 'not-a-token'")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not in Telegram bot-token format', result.stderr)

    def test_telegram_401_is_reported_as_rejected_token(self):
        result = self.run_iskra("printf '%s\\n' '123456:FAKE_SECRET'",
                                '{"ok": false, "error_code": 401, "description": "Unauthorized"}')
        self.assertIn('rejected the bot token (HTTP 401)', result.stderr)
        self.assertNotIn('FAKE_SECRET', result.stdout + result.stderr)
        self.assertNotIn('Unauthorized', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
