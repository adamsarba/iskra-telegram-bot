"""Offline queue checks. No Keychain reads or Telegram requests."""

from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import iskra_ipc as ipc


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(ipc, 'QUEUE', Path(self.temp.name) / 'queue')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        ipc.private_directory(ipc.QUEUE, create=True)

    def pending(self, **changes):
        directory = ipc.QUEUE / ('a' * 32)
        directory.mkdir(mode=0o700)
        data = dict(method='sendMessage', text='private text', expires=time.time() + 30)
        data.update(changes)
        ipc.write_json(directory / 'pending.json', data)
        return directory

    def test_claim_once_receipt_and_content_removal(self):
        directory = self.pending(chat_id='999')
        calls = []
        ipc.process_queue(lambda *args: calls.append(args))
        ipc.process_queue(lambda *args: calls.append(args))
        self.assertEqual(calls, [('sendMessage', {'text': 'private text'})])
        ipc.receipt(directory.name)
        self.assertEqual(list(directory.iterdir()), [directory / 'result.json'])
        self.assertNotIn('private text', (directory / 'result.json').read_text())
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((directory / 'result.json').stat().st_mode & 0o777, 0o600)

    def test_confirmed_result_cleans_content_left_by_interruption(self):
        directory = self.pending()
        (directory / 'pending.json').rename(directory / 'claimed.json')
        ipc.write_json(directory / 'result.json', {'ok': True})
        ipc.process_queue(lambda *args: self.fail('Confirmed request must not be resent'))
        self.assertFalse((directory / 'claimed.json').exists())
        ipc.receipt(directory.name)

    def test_stale_temporary_file_does_not_block_atomic_write(self):
        (ipc.QUEUE / 'health.tmp').write_text('interrupted')
        ipc.write_json(ipc.QUEUE / 'health.json', {'updated': time.time()})
        ipc.check_service()

    def test_maximum_unicode_message_is_processed(self):
        directory = self.pending(text='🌱' * 4096)
        calls = []
        ipc.process_queue(lambda *args: calls.append(args))
        self.assertEqual(len(calls), 1)
        ipc.receipt(directory.name)

    def test_malformed_health_and_receipts_fail_safely(self):
        for value in ([], None, {'updated': 'invalid'}):
            ipc.write_json(ipc.QUEUE / 'health.json', value)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(ipc.main(['--check']), 1)
        directory = self.pending()
        ipc.write_json(directory / 'result.json', [])
        with redirect_stderr(io.StringIO()):
            self.assertEqual(ipc.main(['--receipt', directory.name]), 1)

    def test_expired_request_is_never_sent(self):
        directory = self.pending(expires=time.time() - 1)
        with patch.object(ipc, 'fields_for', wraps=ipc.fields_for):
            calls = []
            ipc.process_queue(lambda *args: calls.append(args))
        self.assertEqual(calls, [])
        self.assertIn('expired', ipc.read_json(directory / 'result.json')['error'])

    def test_interrupted_claim_is_not_retried(self):
        directory = self.pending()
        (directory / 'pending.json').rename(directory / 'claimed.json')
        calls = []
        ipc.process_queue(lambda *args: calls.append(args))
        self.assertEqual(calls, [])
        self.assertIn('unknown', ipc.read_json(directory / 'result.json')['error'])

    def test_transport_error_is_uncertain_and_redacted(self):
        directory = self.pending()
        def send(*args):
            raise RuntimeError('SECRET_TOKEN and response body')
        ipc.process_queue(send)
        outcome = ipc.read_json(directory / 'result.json')
        self.assertIn('not confirmed', outcome['error'])
        self.assertNotIn('SECRET_TOKEN', json.dumps(outcome))

    def test_service_unavailable_does_not_enqueue(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(ipc.main(['hello']), 1)
        self.assertEqual(list(ipc.QUEUE.iterdir()), [])

    def test_symlink_or_public_queue_rejected(self):
        ipc.QUEUE.chmod(0o755)
        with self.assertRaises(ipc.QueueError):
            ipc.private_directory(ipc.QUEUE)
        ipc.QUEUE.chmod(0o700)
        link = Path(self.temp.name) / 'link'
        link.symlink_to(ipc.QUEUE)
        with self.assertRaises(ipc.QueueError):
            ipc.private_directory(link)

    def test_invalid_requests_do_not_send_or_stop_queue(self):
        for changes in ({'text': ''}, {'text': 'x' * 4097}, {'method': 'deleteMessage'},
                        {'expires': float('inf')}, {'expires': 'tomorrow'}):
            with self.subTest(changes=list(changes)):
                directory = self.pending(**changes)
                calls = []
                ipc.process_queue(lambda *args: calls.append(args))
                self.assertEqual(calls, [])
                for child in directory.iterdir():
                    child.unlink()
                directory.rmdir()

    def test_check_only_reads_health(self):
        ipc.write_json(ipc.QUEUE / 'health.json', {'updated': time.time()})
        self.assertEqual(ipc.main(['--check']), 0)
        self.assertEqual(len(list(ipc.QUEUE.iterdir())), 1)

    def test_invalid_json_is_rejected_without_sending(self):
        directory = self.pending()
        (directory / 'pending.json').write_text('not JSON')
        calls = []
        ipc.process_queue(lambda *args: calls.append(args))
        ipc.process_queue(lambda *args: calls.append(args))
        self.assertEqual(calls, [])
        self.assertFalse((directory / 'claimed.json').exists())
        self.assertTrue((directory / 'result.json').exists())

    def test_gif_and_client_service_round_trip(self):
        calls = []
        stop = threading.Event()
        worker = threading.Thread(target=ipc.serve, args=(stop, lambda *args: calls.append(args)))
        worker.start()
        try:
            deadline = time.monotonic() + 2
            while not (ipc.QUEUE / 'health.json').exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            ipc.submit('sendAnimation', 'caption', 'https://example.com/test.gif')
        finally:
            stop.set()
            worker.join(2)
        self.assertEqual(calls, [('sendAnimation', {'animation': 'https://example.com/test.gif', 'caption': 'caption'})])


if __name__ == '__main__':
    unittest.main()
