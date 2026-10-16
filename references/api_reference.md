# NotebookLM Skill API Reference

Command and module reference. NotebookLM is now called Gemini Notebook and lives at `https://notebook.google.com`; `notebooklm.google.com` URLs redirect there and are accepted by every command.

## Running scripts

Always go through the wrapper with its absolute path. It works from any working directory:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py <script>.py [args]
```

`run.py` runs the script with the skill's own `.venv` interpreter. It never creates the venv or installs anything. Before running it checks that:

1. `.venv` exists,
2. `.venv` can `import patchright` (the base interpreter may have been removed or upgraded),
3. `.venv/.requirements.sha256` matches the SHA-256 of `requirements.txt`.

If any check fails it prints the problem and exits **3**. Ask the user before running `setup_environment.py`.

Running a script directly with the system Python fails because `patchright` is only installed in `.venv`.

## Exit codes

| Code | Source | Meaning | Action |
|------|--------|---------|--------|
| 0 | all | Success | |
| 1 | all | Failure (bad args, notebook not found, no answer, error) | Read the output; see troubleshooting |
| 2 | `ask_question.py` | Not authenticated / session expired | Tell the user a browser will open, run `auth_manager.py reauth`, retry once |
| 3 | `run.py` | `.venv` missing, broken or out of date | Ask the user, then run `setup_environment.py` |

## ask_question.py

Ask one question in a fresh browser session.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --question "..."
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --question "..." --notebook-id ID
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --question "..." --notebook-url URL
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --question "..." --show-browser
```

| Option | Description |
|--------|-------------|
| `--question` (required) | Question text. Newlines are joined with spaces (Enter would submit early). |
| `--notebook-id` | Library ID (current slug, legacy ID or a loosely typed name). |
| `--notebook-url` | Notebook URL, either host. Normalized to `https://notebook.google.com/notebook/<id>`. |
| `--show-browser` | Visible browser for this call. |

Notebook resolution order: `--notebook-url`, then `--notebook-id`, then `DEFAULT_NOTEBOOK_ID` from `.env`, then the active notebook. With none of these it lists the library and exits 1. On success the notebook's `use_count` and `last_used` are updated (also for `--notebook-url` when the URL is in the library).

**Output** (stdout, after progress lines):

```
============================================================
Question: <question>
============================================================

<answer text with [n] citations>

[Note to assistant: if this answer leaves a gap in the user's request, ask one self-contained follow-up that restates the needed context; otherwise answer the user.]

============================================================
```

**Answer extraction:** each Q&A in the chat is a `.chat-message-pair` with a `.from-user-container` (question) and `.to-user-container` (answer). The script waits until the newest pair's user bubble matches the question it asked, then until the text stops changing (a copy button appears when an answer is finished). From the answer it removes the collapsible "Thoughts" panel (`thinking-chain-view`), turns citation buttons into `[n]`, prefixes superscripts with `^` and subscripts with `_`, and keeps list and paragraph breaks. Promo dialogs (`mat-dialog-container`) covering the chat are dismissed first. The answer timeout is `QUERY_TIMEOUT_SECONDS` (default 180).

**Side effects:** the question and answer are saved to the notebook's chat history in the user's account (the skill never clears it). Refreshed cookies are saved to `state.json`. On failure, `data/debug/<timestamp>-<reason>.png` and `.html` are written (`no-input`, `no-answer`, `error`).

## notebook_manager.py

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py add \
  --url URL --name NAME --description DESC --topics "t1,t2" [--use-cases "a,b"] [--tags "x,y"]
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py list
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py search --query QUERY
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py activate --id ID
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py remove --id ID
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py stats
```

| Command | Notes |
|---------|-------|
| `add` | `--url`, `--name`, `--description`, `--topics` required. ID = slug of the name (`a-z0-9-`). Rejects a URL already in the library or a duplicate ID (exit 1). The first notebook added becomes active. Prints the new entry as JSON. |
| `list` | Name, ID, topics, use count; the active one is marked `[ACTIVE]`. |
| `search` | Case-insensitive substring match on name, description, topics, tags, use cases. |
| `activate` | Set the default notebook for `ask_question.py`. Exit 1 if not found. |
| `remove` | Remove from the library (not from Google). If it was active, the first remaining notebook becomes active. |
| `stats` | Counts, active and most-used notebook, library path. |

`--id` accepts current IDs, legacy IDs and names (slugified). On load, legacy IDs (which could contain `:` or `&`) are re-keyed to slugs with the old ID kept as `legacy_id`, and stored URLs are normalized to `notebook.google.com`.

**Library entry** (`data/library.json`):

```json
{
  "id": "react-docs",
  "url": "https://notebook.google.com/notebook/abc123",
  "name": "React Docs",
  "description": "...",
  "topics": ["react", "hooks"],
  "content_types": [],
  "use_cases": [],
  "tags": [],
  "created_at": "...",
  "updated_at": "...",
  "use_count": 0,
  "last_used": null
}
```

## auth_manager.py

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py status
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py validate
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py setup [--timeout MIN]
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py reauth [--timeout MIN]
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py clear
```

| Command | Description |
|---------|-------------|
| `status` | Offline check that `state.json` holds an unexpired Google session cookie (`SID`, `__Secure-1PSID`, `__Secure-3PSID`). Prints state age and last login. |
| `validate` | Live headless check against `https://notebook.google.com/login` (redirects to `accounts.google.com` when signed out). Refreshes saved cookies on success; exit 1 if invalid. |
| `setup` | Visible Chrome; the user signs in. Waits up to 10 minutes (`--timeout`). |
| `reauth` | `clear` + `setup`. Use for exit 2 or to switch accounts. |
| `clear` | Delete saved cookies, auth info and the browser profile. |

Tell the user before `setup`/`reauth`: they open a window and wait for a human. `setup --headless` exists but only succeeds if the profile is already signed in. Details: `AUTHENTICATION.md`.

## setup_environment.py

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py            # create/update .venv
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py --check    # report only
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py setup_environment.py --recreate # delete and rebuild .venv
```

The only script that installs anything; ask the user first. It runs on the interpreter that invoked `run.py`, creates `.venv` inside the skill directory, upgrades pip and installs `requirements.txt` (`patchright==1.63.0`, `python-dotenv==1.2.4`) there, and writes `.venv/.requirements.sha256`. It uses the installed Google Chrome and only runs `patchright install chrome` if Chrome is not found in the standard location (that install may ask for sudo). No conda environment is modified.

## cleanup_manager.py

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py cleanup_manager.py                                   # preview
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py cleanup_manager.py --confirm --preserve-library      # delete, keep library
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py cleanup_manager.py --confirm --preserve-library --force  # no prompt
```

Deletes the contents of `data/` (browser state, auth info, debug snapshots, and `library.json` unless `--preserve-library`). `--confirm` without `--force` asks for `yes` on stdin. `.venv` is never deleted.

## Configuration

Optional `${CLAUDE_SKILL_DIR}/.env`, loaded by `config.py`; real environment variables take precedence:

| Variable | Default | Meaning |
|----------|---------|---------|
| `HEADLESS` | `true` | `false` shows the browser on every query |
| `QUERY_TIMEOUT_SECONDS` | `180` | Max wait for an answer |
| `TYPING_DELAY_MS_MIN` / `TYPING_DELAY_MS_MAX` | `15` / `45` | Per-character typing delay |
| `DEFAULT_NOTEBOOK_ID` | unset | Notebook used when no `--notebook-id`/`--notebook-url` is given; takes precedence over the active notebook |

Fixed in `config.py`: login timeout 10 min, page load 30 s, chat input wait 20 s, and all UI selectors.

## Data

```
${CLAUDE_SKILL_DIR}/data/          # git-ignored, never commit
├── library.json
├── auth_info.json
├── browser_state/
│   ├── state.json
│   └── browser_profile/
└── debug/                         # failure screenshots + HTML
```

## Calling from Python

```python
import subprocess
from pathlib import Path

RUN = Path.home() / ".claude/skills/notebooklm/scripts/run.py"

result = subprocess.run(
    ["python3", str(RUN), "ask_question.py", "--question", "...", "--notebook-id", "react-docs"],
    capture_output=True, text=True,
)
if result.returncode == 2:
    ...  # ask the user to run auth_manager.py reauth
elif result.returncode == 3:
    ...  # ask the user to run setup_environment.py
answer = result.stdout
```

Run queries sequentially. Every query launches Chrome on the same profile directory, and a Chrome profile can only be used by one browser process at a time.

## Module classes

Import only from within the venv with `scripts/` on `sys.path`.

### `notebook_manager.NotebookLibrary`
- `add_notebook(url, name, description, topics, content_types=None, use_cases=None, tags=None)`
- `remove_notebook(notebook_id)`, `update_notebook(notebook_id, ...)`
- `resolve_id(notebook_id)`, `get_notebook(notebook_id)`, `list_notebooks()`, `search_notebooks(query)`
- `select_notebook(notebook_id)`, `get_active_notebook()`
- `increment_use_count(notebook_id)`, `get_stats()`

### `auth_manager.AuthManager`
- `is_authenticated()` (offline), `validate_auth()` (live), `get_auth_info()`
- `setup_auth(headless=False, timeout_minutes=10)`, `re_auth(...)`, `clear_auth()`

### `browser_utils`
- `BrowserFactory.launch_persistent_context(playwright, headless=True)`: Chrome on the skill profile with cookies injected
- `BrowserFactory.new_page(context, headless)`: first page, headless UA masked
- `StealthUtils.human_type`, `find_first_visible`, `dismiss_dialogs`, `random_delay`

### `ask_question`
- `ask_notebooklm(question, notebook_url, headless=True)`: returns the answer or `None`; raises `AuthExpired` on a login redirect
