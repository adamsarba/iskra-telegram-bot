# Changelog

## 1.0.0-beta.2 – 2026-11-09

### Added

- `iskra.sh --since` prints the minutes since the last sent message. Only the send time is stored, never the text.
- Pixel art icon in the README, with its Aseprite source in `assets/`.

## 1.0.0-beta.1 – 2026-11-08

### Added

- `/status short` replies with one line per tool showing the limit left.

### Changed

- `/status` shows the time until each reset (`Reset in …`) instead of the percentage used.
- Resets due today or tomorrow show only `today` / `tomorrow` and the time.
- The 10 s reply limit applies to each command separately.

## 1.0.0-alpha.1 – 2026-11-08

### Added

- Telegram notifications for AI coding agents via `iskra.sh`, with optional animations.
- Owner-only `/status` with Claude Code and/or Codex usage limits, in the Mac's time zone.
- macOS LaunchAgent that starts at login.
- README, agent rules template and MIT licence.
