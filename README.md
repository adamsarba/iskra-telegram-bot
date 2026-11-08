# Iskra – Private Telegram Bot

[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-D97757?logo=claude&logoColor=white)](https://code.claude.com/docs/en/quickstart) [![Codex](https://img.shields.io/badge/Codex-supported-000000)](https://learn.chatgpt.com/docs/cli) [![macOS](https://img.shields.io/badge/macOS-only-000000?logo=apple&logoColor=white)](https://www.apple.com/macos/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

Iskra sends short notifications from agents. The `/status` command shows Claude Code and/or Codex usage limits, the percentage left and reset times. It runs locally on a Mac and calls no models when answering this command.

Status: alpha (`1.0.0-alpha.1`) – see the [changelog](CHANGELOG.md).

## Setting it up on your Mac

You need Telegram, Keychain, curl, Python 3.9+ and the Claude Code and/or Codex CLI, installed and signed in. `/status` shows only the ones you use. Check `python3 --version` and `claude auth status` and/or `codex --version`. Installers are on the [Python](https://www.python.org/downloads/macos/), [Claude Code](https://code.claude.com/docs/en/quickstart) and [Codex](https://learn.chatgpt.com/docs/cli) sites. Limits require accounts with a subscription.

1. Put this folder somewhere permanent. Open Terminal in it.
2. In Telegram, open the official `@BotFather`, send `/newbot` and create your own bot. Keep the token to yourself.
3. In **Keychain Access**, add a password item to the "login" keychain. For the name, enter exactly `Iskra - Telegram Bot` – Iskra finds the token by this name. For the account, enter your bot's username (the account is only a description). Paste the token as the password. Keep only one such item on your Mac.
4. Send `/start` to your new bot. Keep its username to yourself until setup is done. Then run the commands below. If macOS asks for access to the Keychain item, allow it.

```sh
chmod 700 iskra.sh
./iskra.sh setup
./iskra.sh "Hi, Iskra works!"
python3 listener.py status
python3 listener.py install
```

`setup` saves the ID of the latest private chat and locks further setup. The test message should reach you. After installing, send `/status` to your bot. On its first run the listener skips earlier messages.

If `codex` only runs inside the app, pass the path to its executable to both Python commands, e.g. `python3 listener.py --codex "/full/path/to/codex" install`. Installing the service remembers that path.

## Everyday use

- In Telegram, send `/status`. The reply is a narrow monospace block. Bars show the limit left. Resets show a short weekday and the date without the year, or `today` / `tomorrow`. The `Updated` footer is when the data was read. Times use your Mac's time zone.
- An agent can send text with `./iskra.sh "Done. You can check the result."` or an animation with `./iskra.sh --gif "https://example.com/animation.gif" "Done!"`.
- The service starts at login. Data is cached for 60 s, and replies are at least 10 s apart.

Copy **[AGENTS-SAMPLE.md](AGENTS-SAMPLE.md)** to `AGENTS.md` and adjust it to your rules. `AGENTS.md` stays local and is ignored by Git. Your coordinator should read the current file before notifying – add a reference with its full path to the coordinator's startup instructions. Writing the rules does not start any agents.

## Stopping and moving

```sh
launchctl bootout "gui/$(id -u)/app.iskra.telegram-status"
```

After renaming or moving the folder, run `python3 listener.py install` again and fix the references in agent instructions. The same command turns a stopped service back on.

Configuration and the log are in `~/.config/iskra/`, the service entry in `~/Library/LaunchAgents/app.iskra.telegram-status.plist`. Account data and tokens are read locally. **Share only the repository**, never your `AGENTS.md`, config or tokens. Everyone sets up their own bot and sign-ins on their own Mac.

## One bot per person

Everyone creates their own bot. Don't share your token – whoever has it fully controls the bot. Two copies of Iskra on one bot would also clash, because Telegram hands each message to only one receiver.

Others can message your bot, but Iskra only answers the owner saved during `setup`.

Names don't clash. A Telegram bot username (`@…_bot`) is globally unique, so BotFather makes you pick a free one. The Keychain item is local to your Mac, so everyone uses the same name, `Iskra - Telegram Bot`.

## Troubleshooting

Check `~/.config/iskra/listener.log`. The listener only answers the owner's `/status` in the saved private chat. It rejects other senders, groups, forwarded messages and commands older than 2 min. After an error, send a fresh command. Saved progress prevents handling the same message twice, but an interrupted send may need the command again.

If Claude limits are unavailable, refresh the sign-in with `claude` → `/login`. Codex uses the App Server `account/rateLimits/read`.

Run the local tests with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_listener.py`. Check the script syntax with `bash -n iskra.sh`.

## Known limitations

- Claude limits come from an undocumented endpoint used by Claude Code. An update may break it.
- Tested on one Mac so far.
- The Mac must be awake, online and signed in.

## Contributing

Contributions are welcome – feel free to open an issue or a pull request. A Linux port is welcome too: the macOS-specific parts are Keychain, Claude Code credentials and the launchd service.

## Author and licence

[Adam Sarba](https://github.com/adamsarba) · [MIT](LICENSE) licence
