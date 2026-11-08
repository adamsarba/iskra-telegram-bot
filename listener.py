#!/usr/bin/python3
"""Owner-only Telegram /status receiver. Uses Python's standard library and curl."""

import argparse
import concurrent.futures
import datetime as dt
import fcntl
import html
import json
import math
import os
from pathlib import Path
import plistlib
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CONFIG = Path.home() / '.config/iskra'
LABEL = 'app.iskra.telegram-status'


def system_timezone():
    # macOS links /etc/localtime to the zone chosen in System Settings.
    try:
        return ZoneInfo(os.path.realpath('/etc/localtime').split('zoneinfo/', 1)[1])
    except (IndexError, ValueError, OSError, ZoneInfoNotFoundError):
        return ZoneInfo('UTC')


TIMEZONE = system_timezone()
TIMEZONE_LABEL = TIMEZONE.key.rsplit('/', 1)[-1].replace('_', ' ')


class Unavailable(Exception):
    """A safe, user-facing failure without response bodies or credentials."""


def save_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def keychain(service, account=None):
    args = ['/usr/bin/security', 'find-generic-password', '-s', service]
    if account:
        args += ['-a', account]
    result = subprocess.run(args + ['-w'], capture_output=True, text=True, timeout=10)
    if result.returncode or not result.stdout.strip():
        raise Unavailable('Keychain entry unavailable')
    return result.stdout.strip()


def request(url, fields=None, headers=()):
    # Secrets enter curl only through stdin, never argv or output/log files.
    config = 'url = ' + json.dumps(url) + '\n'
    config += ''.join('header = ' + json.dumps(h) + '\n' for h in headers)
    args = ['/usr/bin/curl', '-q', '-K', '-', '--silent', '--max-time', '10',
            '--proto', '=https', '--write-out', '\n%{http_code}']
    for name, value in (fields or {}).items():
        args += ['--data-urlencode', name + '=' + str(value)]
    result = subprocess.run(args, input=config, capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise Unavailable('connection failed')
    body, _, status = result.stdout.rpartition('\n')
    if status != '200':
        raise Unavailable('HTTP ' + status)
    try:
        return json.loads(body)
    except ValueError:
        raise Unavailable('invalid JSON response') from None


def telegram(method, fields=None):
    token = keychain('Iskra - Telegram Bot')
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        raise Unavailable('invalid bot token')
    data = request('https://api.telegram.org/bot' + token + '/' + method, fields)
    if data.get('ok') is not True:
        raise Unavailable('Telegram returned ok:false')
    return data['result']


def codex_limits(binary):
    process = subprocess.Popen([binary, 'app-server', '--stdio'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = b''

    def send(value):
        process.stdin.write((json.dumps(value) + '\n').encode())
        process.stdin.flush()

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'iskra', 'version': '0.1.0'}}})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if not selector.select(0.5):
                continue
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                data = json.loads(line)
                if data.get('id') == 1:
                    if 'error' in data:
                        raise Unavailable('Codex initialization failed')
                    send({'method': 'initialized'})
                    send({'id': 2, 'method': 'account/rateLimits/read'})
                elif data.get('id') == 2:
                    if 'error' in data:
                        raise Unavailable('account data unavailable')
                    limits = data['result'].get('rateLimits') or {}
                    return [(w.get('windowDurationMins'), w.get('usedPercent'),
                             w.get('resetsAt')) for w in
                            (limits.get('primary'), limits.get('secondary')) if w]
        raise Unavailable('account read timed out')
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


def claude_limits():
    credentials = json.loads(keychain('Claude Code-credentials'))
    oauth = credentials.get('claudeAiOauth') or {}
    token = oauth.get('accessToken')
    if not token or oauth.get('expiresAt', 0) <= time.time() * 1000:
        raise Unavailable('sign in to Claude Code again')
    # Read-only endpoint used by the installed Claude Code CLI; not a stable public API.
    data = request('https://api.anthropic.com/api/oauth/usage', headers=(
        'Authorization: Bearer ' + token, 'anthropic-beta: oauth-2025-04-20'))
    windows = []
    for key, minutes in (('five_hour', 300), ('seven_day', 10080)):
        window = data.get(key)
        if window:
            reset = window.get('resets_at')
            reset = dt.datetime.fromisoformat(reset.replace('Z', '+00:00')).timestamp() if reset else None
            windows.append((minutes, window.get('utilization'), reset))
    return windows


def window_text(minutes, used, reset, now):
    label = {300: '5h', 10080: '7d'}.get(minutes, str(minutes) + 'm')
    if not isinstance(used, (int, float)) or not math.isfinite(used):
        return label + ' · data unavailable'
    used = round(min(100, max(0, used)))
    remaining = 100 - used
    filled = round(remaining / 10)
    bar = '█' * filled + '░' * (10 - filled)
    line = f'{label} [{bar}] {remaining}% left'
    detail = f'   {used}% used'
    if reset is not None:
        seconds = max(0, reset - now)
        total_minutes = math.ceil(seconds / 60)
        days, remainder = divmod(total_minutes, 1440)
        hours, minutes = divmod(remainder, 60)
        duration = f'{days}d {hours}h' if days else (f'{hours}h {minutes}m' if hours else f'{minutes}m')
        detail += ' · in ' + duration if seconds else ' · reset pending'
        local_reset = dt.datetime.fromtimestamp(reset, TIMEZONE)
        local_now = dt.datetime.fromtimestamp(now, TIMEZONE)
        day_delta = (local_reset.date() - local_now.date()).days
        day = {0: 'today', 1: 'tomorrow'}.get(day_delta) if label == '5h' else None
        day = day or local_reset.strftime('%d.%m')
        weekday = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[local_reset.weekday()]
        day = weekday + ' ' + day
        clock = str(local_reset.hour % 12 or 12)
        if local_reset.minute:
            clock += local_reset.strftime(':%M')
        clock += 'AM' if local_reset.hour < 12 else 'PM'
        return line + '\n' + detail + '\n   ' + day + ' ' + clock
    return line + '\n' + detail


def status_fields(owner, text):
    return {'chat_id': owner, 'text': '<pre>' + html.escape(text) + '</pre>', 'parse_mode': 'HTML'}


def claude_configured():
    # Checks that Claude Code has stored a sign-in, without reading the secret.
    result = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s', 'Claude Code-credentials'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    return result.returncode == 0


def status_text(binary):
    sections = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = []
        if claude_configured():
            jobs.append(('Claude', pool.submit(claude_limits)))
        if binary:
            jobs.append(('Codex', pool.submit(codex_limits, binary)))
        if not jobs:
            sections.append('No Claude Code or Codex sign-in found')
        for name, job in jobs:
            try:
                windows = job.result()
                lines = [window_text(*window, time.time()) for window in windows]
                sections.append(name + '\n' + ('\n'.join(lines) or 'Data unavailable'))
            except Exception as error:
                detail = str(error) if isinstance(error, Unavailable) else 'read failed'
                sections.append(name + '\nData unavailable\n' + textwrap.fill(detail, width=26))
    return '\n\n'.join(sections) + '\n\n' + dt.datetime.now(TIMEZONE).strftime('Updated %H:%M') + ' · ' + TIMEZONE_LABEL


def authorized_status(update, owner, username, now):
    message = update.get('message') or {}
    chat = message.get('chat') or {}
    sender = message.get('from') or {}
    age = now - message.get('date', 0)
    return (chat.get('type') == 'private' and chat.get('id') == owner
            and sender.get('id') == owner and sender.get('is_bot') is False
            and not message.get('forward_origin') and not message.get('forward_date')
            and not message.get('via_bot') and -5 <= age <= 120
            and message.get('text', '').strip() in ('/status', '/status@' + username))


def listen(binary):
    CONFIG.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(CONFIG, 0o700)
    with (CONFIG / 'listener.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        owner = int((CONFIG / 'chat_id').read_text().strip())
        if owner <= 0:
            raise Unavailable('invalid private chat_id')
        me = telegram('getMe')
        chat = telegram('getChat', {'chat_id': owner})
        if chat.get('type') != 'private' or chat.get('id') != owner:
            raise Unavailable('saved chat_id is not the owner private chat')
        cursor = CONFIG / 'offset.json'
        offset = json.loads(cursor.read_text()) if cursor.exists() else None
        if offset is None:
            backlog = telegram('getUpdates', {'offset': -1, 'timeout': 0,
                                             'allowed_updates': '["message"]'})
            offset = backlog[-1]['update_id'] + 1 if backlog else 0
            save_json(cursor, offset)
        cached = ''; cached_at = 0; last_reply = 0
        print('Iskra listener ready', flush=True)
        while True:
            try:
                updates = telegram('getUpdates', {'offset': offset, 'timeout': 5,
                                                 'allowed_updates': '["message"]'})
                save_json(CONFIG / 'health.json', {'last_poll': time.time(), 'pid': os.getpid()})
                for update in updates:
                    if update['update_id'] < offset:
                        continue
                    # Advance durably before sending: retries cannot execute an update twice.
                    offset = update['update_id'] + 1
                    save_json(cursor, offset)
                    now = time.time()
                    if not authorized_status(update, owner, me['username'], now) or now - last_reply < 10:
                        continue
                    last_reply = now
                    if now - cached_at >= 60:
                        cached = status_text(binary)
                        cached_at = time.time()
                    telegram('sendMessage', status_fields(owner, cached))
            except Exception as error:
                detail = str(error) if isinstance(error, Unavailable) else type(error).__name__
                print('Iskra retry · ' + detail, flush=True)
                time.sleep(10)


def install(binary):
    CONFIG.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(CONFIG, 0o700)
    agent = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')
    agent.parent.mkdir(parents=True, exist_ok=True)
    codex = ['--codex', binary] if binary else []
    data = {'Label': LABEL, 'ProgramArguments': [sys.executable, str(Path(__file__).resolve())]
            + codex + ['listen'], 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 15, 'Umask': 0o077,
            'WorkingDirectory': str(Path(__file__).resolve().parent),
            'StandardOutPath': str(CONFIG / 'listener.log'),
            'StandardErrorPath': str(CONFIG / 'listener.log')}
    with agent.open('wb') as stream:
        plistlib.dump(data, stream)
    os.chmod(agent, 0o600)
    subprocess.run(['/bin/launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', str(agent)], check=True)
    print('Iskra LaunchAgent installed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', default=shutil.which('codex'))
    parser.add_argument('command', choices=('status', 'listen', 'install'))
    args = parser.parse_args()
    if args.codex and not Path(args.codex).is_file():
        parser.error('Codex executable not found at ' + args.codex)
    if not args.codex and not claude_configured():
        parser.error('Neither a Claude Code sign-in nor Codex found; pass --codex /absolute/path')
    os.umask(0o077)
    if args.command == 'status':
        print(status_text(args.codex))
    elif args.command == 'install':
        install(args.codex)
    else:
        listen(args.codex)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        detail = str(error) if isinstance(error, Unavailable) else type(error).__name__
        print('Iskra stopped · ' + detail, file=sys.stderr)
        sys.exit(1)
