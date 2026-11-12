"""Private local notification queue. Clients never read credentials or call Telegram."""

import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import uuid

QUEUE = Path('/private/tmp') / ('iskra-' + str(os.getuid()))
TIMEOUT = 30


class QueueError(Exception):
    pass


def private_directory(path, create=False):
    if create:
        path.mkdir(mode=0o700, parents=False, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise QueueError('Local queue must be a private directory owned by this user.')
    return path


def write_json(path, value):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=str(path.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 32768:
        raise QueueError('Invalid local request.')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        raise QueueError('Invalid local request.') from None


def fields_for(request):
    if not isinstance(request, dict):
        raise QueueError('Invalid local request.')
    text = request.get('text')
    method = request.get('method')
    limit = 1024 if method == 'sendAnimation' else 4096
    if not isinstance(text, str) or not text or len(text) > limit:
        raise QueueError('Message is empty or too long.')
    if method == 'sendMessage':
        return method, {'text': text}
    animation = request.get('animation')
    if method != 'sendAnimation' or not isinstance(animation, str) or not animation.startswith('https://') or len(animation) > 2048:
        raise QueueError('Animation must use an HTTPS URL.')
    return method, {'animation': animation, 'caption': text}


def process_queue(send):
    """Claim before calling Telegram. Never retry a claimed request after interruption."""
    for directory in sorted(QUEUE.iterdir()):
        if not re.fullmatch('[0-9a-f]{32}', directory.name):
            continue
        try:
            private_directory(directory)
            result = directory / 'result.json'
            pending = directory / 'pending.json'
            claimed = directory / 'claimed.json'
            if result.exists():
                claimed.unlink(missing_ok=True)
                pending.unlink(missing_ok=True)
                if time.time() - result.stat().st_mtime > 86400:
                    result.unlink()
                    directory.rmdir()
                continue
            if claimed.exists():
                write_json(result, {'ok': False, 'error': 'Delivery unknown after service interruption. Do not resend automatically.'})
                claimed.unlink()
                continue
            if not pending.exists():
                continue
            pending.rename(claimed)
            try:
                request = read_json(claimed)
                method, fields = fields_for(request)
                expires = request.get('expires')
                if not isinstance(expires, (int, float)) or not time.time() < expires <= time.time() + TIMEOUT + 5:
                    raise QueueError('Request expired before sending; no message sent.')
                send(method, fields)
                outcome = {'ok': True}
            except QueueError as error:
                outcome = {'ok': False, 'error': str(error)}
            except Exception:
                # A transport failure may happen after Telegram accepted the request.
                outcome = {'ok': False, 'error': 'Delivery not confirmed. Check Telegram before sending again.'}
            write_json(result, outcome)
            claimed.unlink()
        except (OSError, ValueError, QueueError):
            # Malformed or concurrently removed local files cannot stop the service.
            continue


def serve(stop, send):
    private_directory(QUEUE, create=True)
    while not stop.is_set():
        write_json(QUEUE / 'health.json', {'updated': time.time()})
        process_queue(send)
        stop.wait(0.2)


def receipt(request_id):
    if not re.fullmatch('[0-9a-f]{32}', request_id):
        raise QueueError('Invalid receipt id.')
    directory = private_directory(QUEUE / request_id)
    result = directory / 'result.json'
    if not result.exists():
        raise QueueError('Delivery pending or unknown. Do not resend automatically.')
    outcome = read_json(result)
    if not isinstance(outcome, dict) or not isinstance(outcome.get('ok'), bool):
        raise QueueError('Invalid local receipt. Delivery not confirmed; do not resend automatically.')
    if outcome.get('ok') is not True:
        raise QueueError(outcome.get('error', 'Delivery not confirmed.'))


def check_service():
    private_directory(QUEUE)
    health = read_json(QUEUE / 'health.json')
    if not isinstance(health, dict) or not isinstance(health.get('updated'), (int, float)):
        raise QueueError('Local Iskra service health is invalid; no request submitted.')
    if not 0 <= time.time() - health['updated'] < TIMEOUT:
        raise QueueError('Local Iskra service is unavailable; no request submitted.')


def submit(method, text, animation=None):
    check_service()
    request = {'method': method, 'text': text, 'expires': time.time() + TIMEOUT}
    if animation is not None:
        request['animation'] = animation
    fields_for(request)
    request_id = uuid.uuid4().hex
    directory = private_directory(QUEUE / request_id, create=True)
    write_json(directory / 'pending.json', request)
    deadline = time.monotonic() + TIMEOUT + 5
    while time.monotonic() < deadline:
        if (directory / 'result.json').exists():
            try:
                receipt(request_id)
            except QueueError as error:
                raise QueueError(str(error) + ' Receipt: ' + request_id) from None
            return
        time.sleep(0.1)
    # The deadline prevents a late service restart from sending this request.
    raise QueueError('Delivery not confirmed. Do not resend automatically. Check with iskra.sh --receipt ' + request_id)


def main(args):
    try:
        if args == ['--check']:
            check_service()
        elif len(args) == 2 and args[0] == '--receipt':
            private_directory(QUEUE)
            receipt(args[1])
        elif len(args) == 3 and args[0] == '--gif':
            submit('sendAnimation', args[2], args[1])
        elif len(args) == 1:
            submit('sendMessage', args[0])
        else:
            raise QueueError('Usage: iskra.sh "text" | --gif HTTPS_URL "caption" | --receipt ID')
        return 0
    except (QueueError, OSError, ValueError, KeyError, TypeError) as error:
        detail = str(error) if isinstance(error, QueueError) else 'Local Iskra service is unavailable; check the service installation.'
        print('Iskra: ' + detail, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
