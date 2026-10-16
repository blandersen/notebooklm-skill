# NotebookLM Skill Troubleshooting

All commands use the wrapper: `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py <script> [args]` (abbreviated `run.py` below).

## Quick fixes

| Symptom | Fix |
|---------|-----|
| Exit 3, "Environment not ready" | Ask the user, then `run.py setup_environment.py` |
| Exit 2, "Not authenticated" | Tell the user a window will open, then `run.py auth_manager.py reauth` |
| "Could not find the chat input" | UI drift or overlay; check `data/debug/`, rerun with `--show-browser` |
| "No answer within 180s" | Long answer or UI drift; check `data/debug/`, raise `QUERY_TIMEOUT_SECONDS` |
| "Notebook '...' not found" | `run.py notebook_manager.py list` |
| "Not a notebook URL" | Use `https://notebook.google.com/notebook/<id>` (old host also accepted) |
| "browser may not be secure" on login | See [Google blocks the login](#google-blocks-the-login) |
| Chrome won't start / profile in use | See [Browser won't start](#browser-wont-start-or-the-profile-is-in-use) |

## Environment (exit 3)

`run.py` never installs anything. It exits 3 when:

- `.venv` does not exist,
- `.venv` is broken or lacks `patchright` (e.g. the Python it was built from was removed or upgraded),
- `requirements.txt` changed since setup (hash in `.venv/.requirements.sha256` differs).

Fix, after asking the user (it pip-installs into the skill's own `.venv` only):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py --check     # what's wrong
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py             # install/update
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py --recreate  # base Python gone
```

Needs Python 3.10+ for `python3`. "Google Chrome not found" during setup means Chrome is not in its standard location; setup then tries `patchright install chrome`, which may ask for sudo. Installing Chrome from https://www.google.com/chrome/ is the alternative.

Running a script without `run.py` (`python3 scripts/ask_question.py`) fails with `ModuleNotFoundError: No module named 'patchright'`.

## Authentication

### Not authenticated (exit 2)

Raised when `state.json` has no unexpired Google session cookie, or the notebook page redirects to `accounts.google.com`.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py status    # offline cookie check
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py validate  # live headless check
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py reauth    # visible window, user signs in
```

`status` can say "Yes" while Google has already revoked the session; `validate` is the reliable check. Every successful query and `validate` re-save the rotated cookies, so regular use keeps the session alive.

### Login times out

`setup` waits 10 minutes for the browser to land back on `notebook.google.com`. Give more time with `auth_manager.py setup --timeout 20`. If the user signed in but setup still fails with "no Google session cookie was set", run `reauth`.

### Google blocks the login

"This browser or app may not be secure" is Google's automation detection.

1. Run `reauth` (fresh profile) and let the user sign in by hand in the visible window.
2. Check Chrome is the real Google Chrome and up to date: `setup_environment.py --check`.
3. Do not add a custom user agent or launch flags in `scripts/config.py`. Earlier versions forced a truncated Windows user agent and `--disable-blink-features`, which triggered this block; the current setup uses Patchright's defaults.
4. If it persists, try a different (dedicated) Google account or network.

### Switching accounts

`auth_manager.py reauth` clears the profile and opens a fresh login.

## Queries

### "Could not find the chat input"

The script waits 20 s for `textarea.query-box-input` (fallbacks: `aria-label="Query box"` and older labels). Causes:

- **UI change.** Open `data/debug/<timestamp>-no-input.png` and `.html`, find the new textarea, and update `QUERY_INPUT_SELECTORS` in `scripts/config.py`.
- **Wrong page.** The URL is not a notebook, the notebook was deleted, or the signed-in account has no access. The screenshot shows which.
- **Slow load.** Retry once.

### "No answer within N s"

- A long answer: raise `QUERY_TIMEOUT_SECONDS` in `.env` (default 180).
- The answer structure changed: each Q&A should be a `.chat-message-pair` with `.from-user-container` and `.to-user-container .message-text-content`; completion is signalled by the copy button (`.xap-copy-to-clipboard`). Compare against `data/debug/<timestamp>-no-answer.html` and update `scripts/config.py`.
- The question was not submitted (still in the input box in the screenshot): an overlay or focus problem. Rerun with `--show-browser`.

### Overlay dialogs

Promo / "what's new" dialogs (`mat-dialog-container`) are dismissed before typing. If a new dialog variant is not closed, add its close button to `DIALOG_CLOSE_SELECTORS` in `scripts/config.py`.

### Answer contains "Thoughts" text or odd citations

Answers start with a collapsible "Thoughts" panel (`thinking-chain-view`) that is removed, and citation buttons (`.citation-marker`) become `[n]`. If either shows up raw, the selectors `THOUGHTS_SELECTOR` / `CITATION_SELECTOR` in `scripts/config.py` need updating.

### Wrong or old answer

The skill matches the latest message pair's question to the one it asked, so older chat history should never be returned. If it is, the user-bubble selector (`USER_TEXT_SELECTOR`) has likely drifted.

### Notebook chat history is filling up

Every question the skill asks is saved in the notebook's chat history (visible in the web UI). The skill does not delete it; clear it in the web UI if needed.

### Quota reached

Daily chat limits depend on the user's Google plan. Wait for the reset or use another account with `reauth`. Don't loop retries.

## Browser won't start or the profile is in use

All launches share `data/browser_state/browser_profile/`, and a Chrome profile can only be used by one process. Concurrent queries, or a Chrome left running after a crash, cause launch errors.

```bash
# Find leftover Chrome processes using the skill profile
pgrep -fl "notebooklm/data/browser_state/browser_profile"
pkill -f "notebooklm/data/browser_state/browser_profile"
```

If the profile is corrupted:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py cleanup_manager.py --confirm --preserve-library --force
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py setup
```

`--confirm` without `--force` prompts for `yes` on stdin.

## Library

| Problem | Fix |
|---------|-----|
| ID not found | `notebook_manager.py list`. IDs are slugs (`a-z0-9-`); names and legacy IDs also resolve. |
| "URL already in library as '<id>'" | The notebook is already saved under that ID; use it. |
| "Notebook with ID '...' already exists" | Pick a different `--name`. |
| Old IDs with `:` or `&` | Migrated automatically on load; the old ID still works. |
| Corrupted `library.json` | Back it up, delete it, re-add notebooks. |

## Debugging

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --question "test" --show-browser
ls -t ${CLAUDE_SKILL_DIR}/data/debug/ | head
```

Set `HEADLESS=false` in `${CLAUDE_SKILL_DIR}/.env` to see the browser on every call.

Useful information for a bug report: `setup_environment.py --check`, `auth_manager.py status`, the command and its full output, and the latest `data/debug/` screenshot (the HTML dump may contain notebook content; review before sharing). Never share `data/browser_state/`.

## Full reset

```bash
cp ${CLAUDE_SKILL_DIR}/data/library.json ~/library.backup.json          # optional backup
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py cleanup_manager.py --confirm --preserve-library --force
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py --recreate   # ask the user first
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py setup
```
