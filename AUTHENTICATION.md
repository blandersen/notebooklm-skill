# Authentication Architecture

## Overview

The skill signs in to Google once in a visible Chrome window and reuses that session for headless queries. It combines two mechanisms:

1. **Persistent Chrome profile** (`data/browser_state/browser_profile/`, passed as `user_data_dir`) so the browser looks the same across launches and keeps persistent cookies and cache.
2. **Cookie injection** from `data/browser_state/state.json` on every launch, because session cookies are not restored from the profile (Playwright bug below).

## Why both

Playwright/Patchright bug [#36139](https://github.com/microsoft/playwright/issues/36139): with `launch_persistent_context()`, cookies without an expiry date (session cookies) are not restored from `user_data_dir` after a restart. Some Google auth cookies are session cookies, so profile-only auth fails intermittently.

`launch_persistent_context()` in Python also has no `storage_state` option ([#14949](https://github.com/microsoft/playwright/issues/14949)), so the cookies are saved with `context.storage_state()` and re-added with `context.add_cookies()`.

## Flow

### Login: `auth_manager.py setup`

1. Launch Chrome (visible) on the persistent profile.
2. Open `https://notebook.google.com/login`. When signed out, Google redirects server-side to `accounts.google.com`.
3. The user signs in. The script waits up to 10 minutes (`--timeout MIN`) for the page to return to `notebook.google.com`.
4. Require a Google session cookie (`SID`, `__Secure-1PSID` or `__Secure-3PSID`), then save all cookies to `state.json` and the login time to `auth_info.json`.

If the profile is already signed in, setup saves the state and returns immediately.

### Every launch: `BrowserFactory.launch_persistent_context()` (`scripts/browser_utils.py`)

```python
context = playwright.chromium.launch_persistent_context(  # Playwright's Chromium-family API
    user_data_dir=str(BROWSER_PROFILE_DIR),
    channel="chrome",        # real Google Chrome
    headless=headless,
    no_viewport=True,
    args=BROWSER_ARGS + (HEADLESS_ARGS if headless else []),
)
context.add_cookies(json.load(open(STATE_FILE))["cookies"])  # #36139 workaround
```

### After every successful query

`ask_question.py` saves the context's cookies back to `state.json`. Google rotates session cookies, so this keeps the saved session current. `auth_manager.py validate` does the same.

## Commands

| Command | What it does | Opens a window |
|---------|--------------|----------------|
| `status` | Offline: does `state.json` contain an unexpired Google session cookie? Warns if the state is older than 14 days. | No |
| `validate` | Live headless check: loads `https://notebook.google.com/login`; valid if it stays on the app instead of redirecting to `accounts.google.com`. Re-saves cookies on success; exits 1 if invalid. | No |
| `setup` | Interactive login as above. | Yes |
| `reauth` | `clear`, then `setup`. Also the way to switch Google accounts. | Yes |
| `clear` | Delete `state.json`, `auth_info.json` and the whole `browser_state/` directory (including the profile). | No |

Run with `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py <command>`.

`ask_question.py` exits with code 2 when there is no saved session or Google redirects to the login page. The fix is `reauth`.

## Anti-detection

Google's sign-in page rejects browsers it considers automated ("This browser or app may not be secure"). The skill follows Patchright's recommended configuration and avoids adding its own fingerprint:

- Real Google Chrome (`channel="chrome"`), not a bundled browser build.
- `no_viewport=True`; no custom user agent and no extra headers. (Earlier versions forced a truncated Windows user agent, which is a strong bot signal, plus `--no-sandbox` and `--disable-blink-features` flags. All removed; Patchright handles this itself.)
- Extra launch flags are only `--no-first-run` and `--no-default-browser-check`.
- In headless mode the window is 1440x900, and the `HeadlessChrome` token is replaced with `Chrome` in both `navigator.userAgent` and the client hints (`userAgentData` brands and full version list) via the CDP `Network.setUserAgentOverride` command.
- Questions are typed character by character with 15-45 ms delays (`TYPING_DELAY_MS_MIN/MAX`); questions over 400 characters are filled in at once.

Login always happens in a visible window by the user. The skill never enters credentials.

## Files

```
~/.claude/skills/notebooklm/data/
├── auth_info.json           # Time of last successful login
└── browser_state/
    ├── state.json           # Cookies + localStorage, injected on every launch
    └── browser_profile/     # Chrome user profile (fingerprint, persistent cookies, cache)
```

`state.json` grants access to the Google account. It is git-ignored with the rest of `data/`; never commit or share it.

## Code references

- `scripts/browser_utils.py`: `BrowserFactory.launch_persistent_context`, `_inject_cookies`, `new_page` / `_mask_headless_user_agent`
- `scripts/auth_manager.py`: `has_session_cookie`, `AuthManager.is_authenticated` (status), `setup_auth`, `validate_auth`, `clear_auth`, `re_auth`
- `scripts/ask_question.py`: `ask_notebooklm` (login-redirect detection, cookie re-save)
- `scripts/config.py`: `BROWSER_ARGS`, `HEADLESS_ARGS`, `LOGIN_TIMEOUT_MINUTES`, URLs

## Related issues

- [microsoft/playwright#36139](https://github.com/microsoft/playwright/issues/36139): session cookies not restored with persistent context
- [microsoft/playwright#14949](https://github.com/microsoft/playwright/issues/14949): storage state with persistent context
