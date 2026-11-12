#!/bin/bash
# Usage: iskra.sh setup | iskra.sh "text" | iskra.sh --gif URL "caption" | iskra.sh --since | iskra.sh --receipt ID | iskra.sh --check
set -eu
set +x
fail() { printf 'Iskra: %s\n' "$*" >&2; exit 1; }
dir="$HOME/.config/iskra"
if [ "$#" -eq 1 ] && [ "$1" = --since ]; then
  # Minutes since the last successful send, or "none"; reads only a timestamp.
  last=$(cat "$dir/last-sent" 2>/dev/null || true)
  if [[ "$last" =~ ^[0-9]+$ ]]; then echo $(( ($(date +%s) - last) / 60 )); else echo none; fi
  exit 0
elif [ "$#" -eq 1 ] && [ "$1" = setup ]; then
  # Lock: once a chat is saved, a stranger messaging the bot cannot take it over.
  [ ! -e "$dir/chat_id" ] || fail "Chat id already saved; delete $dir/chat_id yourself to redo setup."
elif { [ "$#" -eq 3 ] && [ "$1" = --gif ]; } || { [ "$#" -eq 2 ] && [ "$1" = --receipt ]; } || [ "$#" -eq 1 ]; then
  # The local service owns Keychain access and Telegram requests.
  script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
  exec python3 "$script_dir/iskra_ipc.py" "$@"
elif [ "$#" -ne 1 ]; then
  fail 'Usage: iskra.sh setup | iskra.sh "text" | iskra.sh --gif URL "caption" | iskra.sh --since | iskra.sh --receipt ID | iskra.sh --check'
fi
token=$(security find-generic-password -s "Iskra - Telegram Bot" -w 2>/dev/null) || fail 'Could not read the Iskra token from Keychain. The item may be missing, or macOS may have denied access. Check that the login Keychain is unlocked and the item is named "Iskra - Telegram Bot". If prompted, approve access for this run; if running in a sandbox, ask the authorized user to rerun this command through the normal approval flow outside the sandbox.'
[[ "$token" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || fail 'The Keychain item was read, but its value is not in Telegram bot-token format. Check the item in Keychain Access; do not paste the token into chat or logs.'
set -- --data-urlencode 'allowed_updates=["message"]'
response=$(printf 'url = "https://api.telegram.org/bot%s/%s"\n' "$token" getUpdates |
  curl -q -K - --silent --show-error --max-time 10 "$@") || fail 'Telegram request failed.'
unset token
# Tokenize JSON in Bash, including escaped strings; no external JSON dependency.
pattern='^("([^"\\]|\\.)*"|-?[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?|true|false|null|[][{}:,])'
depth=0; cdpth=0; id=; kind=; latest=; ok=; error_code=; prev=; before=
while [ -n "$response" ]; do
  response="${response#"${response%%[!$' \t\r\n']*}"}"
  [ -n "$response" ] || break
  [[ "$response" =~ $pattern ]] || fail 'Invalid JSON response from Telegram.'
  t=${BASH_REMATCH[1]}; response=${response:${#t}}
  if [ "$depth" -eq 1 ] && [ "$before:$prev" = '"ok"::' ]; then ok=$t; fi
  if [ "$depth" -eq 1 ] && [ "$before:$prev" = '"error_code"::' ]; then error_code=$t; fi
  if [ "$cdpth" -gt 0 ] && [ "$depth" -eq "$cdpth" ]; then
    [ "$before:$prev" != '"id"::' ] || id=$t
    [ "$before:$prev" != '"type"::' ] || kind=$t
  fi
  case "$t" in
    '{'|'[')
      depth=$((depth + 1))
      if [ "$t:$before:$prev" = '{:"chat"::' ]; then cdpth=$depth; id=; kind=; fi ;;
    '}'|']')
      if [ "$cdpth" -eq "$depth" ]; then
        if [ "$kind" = '"private"' ] && [[ "$id" =~ ^[0-9]+$ ]]; then latest=$id; fi
        cdpth=0
      fi
      depth=$((depth - 1)) ;;
  esac
  before=$prev; prev=$t
done
if [ "$ok" != true ]; then
  [ "$error_code" != 401 ] || fail 'Telegram rejected the bot token (HTTP 401). Check that the Keychain item contains the current token from BotFather.'
  fail 'Telegram API returned ok:false or an invalid response.'
fi
[ -n "$latest" ] || fail 'No private chat found; send /start to the bot, then retry setup.'
umask 077; mkdir -p "$dir"; chmod 700 "$dir"
printf '%s\n' "$latest" > "$dir/chat_id"; chmod 600 "$dir/chat_id"
printf 'Chat id saved: %s\n' "$latest"
