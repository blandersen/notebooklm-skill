# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-16

First release of the maintained fork ([blandersen/notebooklm-skill](https://github.com/blandersen/notebooklm-skill)) of the archived upstream [PleasePrompto/notebooklm-skill](https://github.com/PleasePrompto/notebooklm-skill).

### Changed
- **Gemini Notebook rename**: Google renamed NotebookLM to Gemini Notebook (July 16, 2026) and moved it to `https://notebook.google.com`. Both the new host and the redirecting `notebooklm.google.com` are accepted; URLs are normalized to `notebook.google.com`. The skill keeps the name `notebooklm`.
- **Absolute script paths**: skill commands are `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py <script>` and work from any working directory (the old relative `python scripts/run.py` only worked from the skill dir).
- **No implicit installs**: `run.py` no longer creates the venv or installs packages. If `.venv` is missing, broken or out of date (SHA-256 of `requirements.txt` in `.venv/.requirements.sha256`), it exits 3 so the user can be asked before running `setup_environment.py` (`--check`, `--recreate`).
- `setup_environment.py` installs into the skill's own `.venv` only, uses the installed Google Chrome (`channel="chrome"`) and runs `patchright install chrome` only when Chrome is missing.
- Dependencies: `patchright==1.63.0`, `python-dotenv==1.2.4`. Python 3.10+.
- **Authentication**: `status` is an offline check for an unexpired Google session cookie (`SID`, `__Secure-1PSID`, `__Secure-3PSID`); `validate` is a live headless check against `https://notebook.google.com/login` and refreshes saved cookies. Cookies are also re-saved after every successful query.
- **Anti-detection**: follow Patchright's recommended config (`channel="chrome"`, `no_viewport=True`, no custom user agent or headers). In headless mode `HeadlessChrome` is replaced in both `navigator.userAgent` and client hints via CDP; headless window is 1440x900.
- **Answer extraction** for the current UI: chat input `textarea.query-box-input`; answers are read from the newest `.chat-message-pair` whose question matches the one asked, so persisted chat history is never returned; the "Thoughts" panel is stripped, citations become `[n]`, superscripts `^`; completion is detected via the copy button. Promo dialogs are dismissed.
- **Exit codes** from `ask_question.py`: 0 ok, 1 failure, 2 not authenticated (run `auth_manager.py reauth`), 3 environment not ready (from `run.py`).
- **Library IDs** are shell-safe slugs (`a-z0-9-`); legacy IDs containing `:` or `&` are migrated on load and still resolve. Stored URLs are normalized.
- Follow-up note appended to answers is now a calm `[Note to assistant: ...]` (previously "EXTREMELY IMPORTANT: Is that ALL you need to know?"); at most 2 self-contained follow-ups.
- Default answer timeout is 180 s (`QUERY_TIMEOUT_SECONDS`).
- Documentation rewritten to match the code.

### Fixed
- `.env` is actually loaded (it was documented but ignored): `HEADLESS`, `QUERY_TIMEOUT_SECONDS`, `TYPING_DELAY_MS_MIN/MAX`, `DEFAULT_NOTEBOOK_ID`.
- Google "browser may not be secure" login blocks caused by the forced, truncated Windows user agent and extra Chrome flags.
- Adding a URL already in the library is rejected instead of creating a duplicate.
- `use_count` / `last_used` are updated after each successful query.

### Added
- Failure snapshots (screenshot + HTML) in `data/debug/` when the chat input or answer can't be found, to diagnose UI drift.
- Automatic dismissal of "what's new" dialogs (`mat-dialog-container`) covering the chat.
- `setup_environment.py --check` and `--recreate`.

### Removed
- `browser_session.py` (unused and broken).
- Custom user agent, `--no-sandbox` and `--disable-blink-features` launch flags.
- Documentation of settings that never existed (`STEALTH_ENABLED`, `SHOW_BROWSER`, `TYPING_WPM_*`) and of fixed daily quota numbers; quotas depend on the user's Google plan.

## [1.3.0] - 2025-11-21

### Added
- **Modular Architecture** - Refactored codebase for better maintainability
  - New `config.py` - Centralized configuration (paths, selectors, timeouts)
  - New `browser_utils.py` - BrowserFactory and StealthUtils classes
  - Cleaner separation of concerns across all scripts

### Changed
- **Timeout increased to 120 seconds** - Long queries no longer timeout prematurely
  - `ask_question.py`: 30s → 120s
  - `browser_session.py`: 30s → 120s
  - Resolves Issue #4

### Fixed
- **Thinking Message Detection** - Fixed incomplete answers showing placeholder text
  - Now waits for `div.thinking-message` element to disappear before reading answer
  - Answers like "Reviewing the content..." or "Looking for answers..." no longer returned prematurely
  - Works reliably across all languages and NotebookLM UI changes

- **Correct CSS Selectors** - Updated to match current NotebookLM UI
  - Changed from `.response-content, .message-content` to `.to-user-container .message-text-content`
  - Consistent selectors across all scripts

- **Stability Detection** - Improved answer completeness check
  - Now requires 3 consecutive stable polls instead of 1 second wait
  - Prevents truncated responses during streaming

## [1.2.0] - 2025-10-28

### Added
- Initial public release
- NotebookLM integration via browser automation
- Session-based conversations with Gemini 2.5
- Notebook library management
- Knowledge base preparation tools
- Google authentication with persistent sessions
