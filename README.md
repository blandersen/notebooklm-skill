> [!NOTE]
> This is a maintained fork of [PleasePrompto/notebooklm-skill](https://github.com/PleasePrompto/notebooklm-skill), which was archived in September 2026. Fork: [blandersen/notebooklm-skill](https://github.com/blandersen/notebooklm-skill).

<div align="center">

# NotebookLM Claude Code Skill

**Let [Claude Code](https://github.com/anthropics/claude-code) ask your Google NotebookLM (now "Gemini Notebook") notebooks questions and get source-grounded, citation-backed answers drawn only from the documents you uploaded.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-purple.svg)](https://www.anthropic.com/news/skills)

[Installation](#installation) • [Quick Start](#quick-start) • [How It Works](#how-it-works) • [Commands](#commands) • [Limitations](#limitations)

</div>

---

## NotebookLM is now Gemini Notebook

Google renamed NotebookLM to **Gemini Notebook** on July 16, 2026 and moved the app to `https://notebook.google.com`. Old `https://notebooklm.google.com/...` links 301-redirect to the new host. The skill accepts both URL forms and stores them as `notebook.google.com` URLs. The skill itself keeps its name, `notebooklm` (invoked as `/notebooklm`).

## Local Claude Code only

The skill drives a real Google Chrome window on your machine, so it needs local [Claude Code](https://github.com/anthropics/claude-code) with network access. It does not work in sandboxed environments such as the Claude web UI.

---

## What it does

Instead of having Claude read through your documentation file by file (expensive and prone to filling gaps with guesses), you upload the documents to a notebook once and let Claude ask the notebook. Gemini answers only from the notebook's sources and cites them, and Claude uses the answer for the task at hand:

```
Your task → Claude asks your notebook → source-grounded answer with citations → Claude continues the task
```

There is no copy-paste between the browser and the terminal, and no vector database, embeddings or chunking to set up.

---

## Requirements

- macOS, Linux or Windows with **Google Chrome** installed (real Chrome, driven via Patchright's `channel="chrome"`)
- Python 3.10+ (used only to create the skill's own `.venv`)
- A Google account with access to the notebooks you want to query

## Installation

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/blandersen/notebooklm-skill ~/.claude/skills/notebooklm

# Create the skill's .venv and install its pinned dependencies into it
python3 ~/.claude/skills/notebooklm/scripts/run.py setup_environment.py
```

`setup_environment.py`:
- creates `~/.claude/skills/notebooklm/.venv` and pip-installs `requirements.txt` there (`patchright==1.63.0`, `python-dotenv==1.2.4`); no other Python environment is touched
- uses your existing Google Chrome, and only runs `patchright install chrome` if Chrome is not found
- writes a hash of `requirements.txt` to `.venv/.requirements.sha256` so `run.py` can detect an outdated venv

Options: `--check` (report status only), `--recreate` (delete and rebuild `.venv`, e.g. after the base Python was removed or upgraded).

`run.py` never installs anything itself. If `.venv` is missing, broken or out of date it exits with code 3 and prints the setup command; when Claude sees that, it asks you before running setup.

---

## Quick Start

1. **Authenticate (one-time).** In Claude Code say *"Set up NotebookLM authentication"*. A Chrome window opens; sign in to Google. The skill waits up to 10 minutes.
2. **Create a notebook** at [notebook.google.com](https://notebook.google.com) and add your sources (PDFs, Google Docs, websites, YouTube videos, ...). Sources can only be added in the web UI.
3. **Add it to the library.** *"Add this notebook to my library: <link>"*. If you don't give a description, Claude asks the notebook what it contains and uses that.
4. **Ask.** *"What does my React notebook say about hooks?"*

Notebooks in the signed-in account work as-is. Notebooks owned by someone else must be shared with that account (or with anyone who has the link).

---

## How It Works

Each question is one script run:

1. `run.py` checks the skill's `.venv` and runs `ask_question.py` with it.
2. Chrome starts headless on the skill's persistent profile, and saved Google cookies are injected (see [AUTHENTICATION.md](AUTHENTICATION.md)).
3. The notebook opens, any "what's new" promo dialog is dismissed, the question is typed into the chat box and submitted.
4. The script waits for the answer that belongs to this question, strips the collapsible "Thoughts" panel, renders inline citations as `[n]`, and prints it.
5. Refreshed Google cookies are saved and the browser closes.

A query takes roughly 20-25 seconds, mostly browser startup and answer generation.

**Chat history.** Every question the skill asks is saved to that notebook's chat history in your account and is visible in the web UI. The skill does not clear it. It picks out its own answer by matching the latest message pair against the question it just asked, so older history is never returned. Whether Gemini uses earlier turns as context is not guaranteed, so follow-up questions are written to be self-contained.

**Follow-ups.** Each answer ends with a short `[Note to assistant: ...]` line. Claude asks at most two self-contained follow-ups when an answer leaves a real gap, then synthesizes the result for you.

**Failure snapshots.** If the chat input or an answer can't be found, a screenshot and HTML dump are written to `data/debug/`. UI selectors live in `scripts/config.py`.

### Layout

```
~/.claude/skills/notebooklm/
├── SKILL.md                  # Instructions Claude reads
├── scripts/
│   ├── run.py                # Wrapper: runs a script with the skill's .venv (never installs)
│   ├── setup_environment.py  # Creates/updates .venv (the only script that installs)
│   ├── ask_question.py       # Ask one question
│   ├── notebook_manager.py   # Notebook library
│   ├── auth_manager.py       # Google login and session checks
│   ├── cleanup_manager.py    # Delete skill data
│   ├── browser_utils.py      # Chrome launch, cookie injection, typing
│   └── config.py             # URLs, selectors, timeouts, .env loading
├── .venv/                    # Created by setup_environment.py
└── data/                     # Library, auth state, debug snapshots (git-ignored)
```

---

## Commands

You normally talk to Claude in plain language (*"Show my notebooks"*, *"Use the React notebook"*, *"Reset NotebookLM authentication"*). The underlying commands, runnable from any directory:

```bash
S=~/.claude/skills/notebooklm/scripts/run.py

# Ask (active notebook unless --notebook-id / --notebook-url is given)
python3 $S ask_question.py --question "..." [--notebook-id ID | --notebook-url URL] [--show-browser]

# Authentication
python3 $S auth_manager.py status     # offline: is a non-expired Google session cookie saved?
python3 $S auth_manager.py validate   # live headless check; also refreshes saved cookies
python3 $S auth_manager.py setup      # visible Chrome, sign in (waits up to 10 min, --timeout MIN)
python3 $S auth_manager.py reauth     # clear browser state, then setup
python3 $S auth_manager.py clear      # delete saved auth

# Library
python3 $S notebook_manager.py add --url URL --name NAME --description DESC --topics "t1,t2" [--use-cases "..."] [--tags "..."]
python3 $S notebook_manager.py list
python3 $S notebook_manager.py search --query Q
python3 $S notebook_manager.py activate --id ID
python3 $S notebook_manager.py remove --id ID
python3 $S notebook_manager.py stats

# Cleanup (preview by default)
python3 $S cleanup_manager.py [--confirm] [--preserve-library] [--force]
```

`ask_question.py` exit codes: `0` answer printed, `1` failure, `2` not authenticated or session expired (run `auth_manager.py reauth`), `3` environment not ready (from `run.py`).

Library IDs are shell-safe slugs generated from the name (`a-z0-9-`). IDs from older versions (which could contain `:` or `&`) are migrated automatically and still resolve. Adding a URL that is already in the library is rejected.

---

## Configuration

Optional `~/.claude/skills/notebooklm/.env` (real environment variables take precedence):

```env
HEADLESS=true              # false = always show the browser (per call: --show-browser)
QUERY_TIMEOUT_SECONDS=180  # max wait for an answer
TYPING_DELAY_MS_MIN=15     # per-character typing delay
TYPING_DELAY_MS_MAX=45
DEFAULT_NOTEBOOK_ID=       # used when no --notebook-id/--notebook-url is given (before the active notebook)
```

## Data

Everything is stored in `~/.claude/skills/notebooklm/data/`, which is git-ignored. Never commit or share it.

```
data/
├── library.json          # Notebook library
├── auth_info.json        # Time of last successful login
├── browser_state/
│   ├── state.json        # Saved cookies (injected on every launch)
│   └── browser_profile/  # Chrome profile
└── debug/                # Screenshots + HTML from failed queries
```

---

## Limitations

- **UI automation.** There is no official consumer API, so the skill drives the web UI. Google UI changes can break the selectors in `scripts/config.py`; `data/debug/` snapshots help update them.
- **One question per browser session**, about 20-25 s each. Queries share one Chrome profile, so run them one at a time.
- **Quotas** depend on your Google plan (the paid tiers were reshuffled in 2026). Check your plan's chat limits.
- **Sources** must be added in the web UI.
- **Chat history** in the notebook grows with every question the skill asks.

## Alternatives

- [teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py): unofficial Python client that calls Google's internal `batchexecute` RPC instead of automating the page. Faster, but depends on an undocumented API.
- [PleasePrompto/notebooklm-mcp](https://github.com/PleasePrompto/notebooklm-mcp): the original author's MCP server version (TypeScript), usable from other MCP clients.
- The official Gemini Notebook Enterprise API is only available to Google Cloud enterprise customers and covers notebook management, not consumer chat.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Skill not found | `ls ~/.claude/skills/notebooklm/SKILL.md` |
| Exit 3 / "Environment not ready" | `python3 ~/.claude/skills/notebooklm/scripts/run.py setup_environment.py` (`--recreate` if the venv's base Python is gone) |
| Exit 2 / not authenticated | `python3 ~/.claude/skills/notebooklm/scripts/run.py auth_manager.py reauth` |
| "Could not find the chat input" / "No answer" | Inspect `data/debug/`, or rerun with `--show-browser` |
| Corrupted browser profile | `cleanup_manager.py --confirm --preserve-library`, then `auth_manager.py setup` |

More in [references/troubleshooting.md](references/troubleshooting.md).

---

## Disclaimer

This tool automates a Google web app. It uses real Chrome with Patchright's recommended settings and human-like typing delays, but Google may still detect or restrict automated use. Consider using a dedicated Google account. Your credentials are entered by you in a local Chrome window and never handled by the skill; the saved cookies in `data/` grant access to your account, so keep that directory private.

AI coding agents make mistakes. Review what they do before relying on it.

---

## Credits and license

Originally created by [PleasePrompto](https://github.com/PleasePrompto) as a Claude Code adaptation of the [NotebookLM MCP Server](https://github.com/PleasePrompto/notebooklm-mcp). This fork is maintained at [blandersen/notebooklm-skill](https://github.com/blandersen/notebooklm-skill). MIT License, see [LICENSE](LICENSE).
