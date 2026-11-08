# Iskra – simple rules template

In your copy of the project, save this template as `AGENTS.md`. Adjust the rules and add the full path to this file to your agent's startup instructions.

## When to notify

- Send a message when the user asks for it or agrees to a notification after a specific task.
- After checking the result, send one short summary. Keep ongoing details in the conversation.
- Read the current file before sending. Record agreed rule changes here.

## What is available

- `./iskra.sh "Text"` sends plain text to the configured owner.
- `./iskra.sh --gif "https://example.com/animation.gif" "Caption"` sends an animation with a caption, when the user wants it.
- `/status`, sent by the owner in Telegram, shows the available Codex and Claude limits. A local service handles it.

Run commands from the Iskra folder or by full path. Keep the token in Keychain and keep the owner binding. Pass message text as data, with safe quoting.

## How to write

Short, plain, in the user's language. Give the result and, if needed, one thing to check.

> Done! The photos are sorted. You can take a look in the folder.

> The export stopped. I need you to pick a format – details are in the chat.

If sending fails, tell the user in the current conversation. Send only content the user has agreed to, and never secrets.
