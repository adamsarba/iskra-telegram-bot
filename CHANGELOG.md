# Changelog

## 1.0.0-beta.3 – 2026-11-12

### Added

- Local outgoing queue handled by the existing listener. Normal sends no longer read Keychain or contact Telegram in the agent process.
- `iskra.sh --check` checks sending-service availability; `--receipt ID` checks uncertain outcomes. Requests expire before sending and interrupted sends are never retried automatically.

### Changed

- Offline regression tests are grouped in `tests/` and run with unittest discovery.

### Fixed

- Keychain read failures now explain that the item may be missing or access denied, and provide safe recovery guidance. Invalid token format and Telegram HTTP 401 have separate diagnostics.
- Atomic queue writes recover from interrupted writes; valid Unicode messages fit within the queue payload limit.
- Malformed service health and receipts return safe errors.
- Offline regressions cover queue delivery, expiration, interrupted sends, private permissions, token diagnostics and secret redaction.

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
