#!/bin/bash
# Usage: iskra.sh setup | iskra.sh "text" | iskra.sh --gif URL "caption"
set -eu
set +x
fail() { printf 'Iskra: %s\n' "$*" >&2; exit 1; }
dir="$HOME/.config/iskra"
mode=sendMessage
if [ "$#" -eq 1 ] && [ "$1" = setup ]; then
  # Lock: once a chat is saved, a stranger messaging the bot cannot take it over.
  [ ! -e "$dir/chat_id" ] || fail "Chat id already saved; delete $dir/chat_id yourself to redo setup."
  mode=getUpdates
elif [ "$#" -eq 3 ] && [ "$1" = --gif ]; then
  mode=sendAnimation
elif [ "$#" -ne 1 ]; then
  fail 'Usage: iskra.sh setup | iskra.sh "text" | iskra.sh --gif URL "caption"'
fi
token=$(security find-generic-password -s "Iskra - Telegram Bot" -w 2>/dev/null) || fail 'Bot token missing from Keychain.'
[[ "$token" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || fail 'Bot token missing or invalid in Keychain.'
if [ "$mode" != getUpdates ]; then
  [ -r "$dir/chat_id" ] || fail 'Chat id missing; send /start to the bot, then run iskra.sh setup.'
  chat=$(<"$dir/chat_id")
  [[ "$chat" =~ ^[0-9]+$ ]] || fail 'Stored chat id is invalid; run setup again.'
  if [ "$mode" = sendAnimation ]; then
    set -- --data-urlencode "chat_id=$chat" --data-urlencode "animation=$2" --data-urlencode "caption=$3"
  else
    set -- --data-urlencode "chat_id=$chat" --data-urlencode "text=$1"
  fi
else
  set -- --data-urlencode 'allowed_updates=["message"]'
fi
response=$(printf 'url = "https://api.telegram.org/bot%s/%s"\n' "$token" "$mode" |
  curl -q -K - --silent --show-error --max-time 10 "$@") || fail 'Telegram request failed.'
unset token
# Tokenize JSON in Bash, including escaped strings; no external JSON dependency.
pattern='^("([^"\\]|\\.)*"|-?[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?|true|false|null|[][{}:,])'
depth=0; cdpth=0; id=; kind=; latest=; ok=; prev=; before=
while [ -n "$response" ]; do
  response="${response#"${response%%[!$' \t\r\n']*}"}"
  [ -n "$response" ] || break
  [[ "$response" =~ $pattern ]] || fail 'Invalid JSON response from Telegram.'
  t=${BASH_REMATCH[1]}; response=${response:${#t}}
  if [ "$depth" -eq 1 ] && [ "$before:$prev" = '"ok"::' ]; then ok=$t; fi
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
[ "$ok" = true ] || fail 'Telegram API returned ok:false or an invalid response.'
if [ "$mode" = getUpdates ]; then
  [ -n "$latest" ] || fail 'No private chat found; send /start to the bot, then retry setup.'
  umask 077; mkdir -p "$dir"; chmod 700 "$dir"
  printf '%s\n' "$latest" > "$dir/chat_id"; chmod 600 "$dir/chat_id"
  printf 'Chat id saved: %s\n' "$latest"
fi
