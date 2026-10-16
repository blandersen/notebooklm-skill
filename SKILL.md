---
name: notebooklm
description: Query the user's Google NotebookLM (now "Gemini Notebook", notebook.google.com) notebooks for source-grounded, citation-backed answers drawn only from the documents they uploaded. Use when the user mentions NotebookLM or Gemini Notebook, shares a notebook.google.com or notebooklm.google.com notebook URL, or asks to query, add, or manage their notebooks.
argument-hint: "[question | notebook URL]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/run.py *)
---

# NotebookLM / Gemini Notebook Research Assistant

Google renamed NotebookLM to **Gemini Notebook** (July 2026) and moved it to `https://notebook.google.com`. Old `notebooklm.google.com` links redirect and are accepted everywhere below.

Each question opens a fresh browser session on the notebook, asks once, returns the answer, and closes. There is no memory between questions.

## Running scripts

Always run through the wrapper with the absolute path. It works from any working directory:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py <script>.py [args]
```

Exit codes worth acting on:

| Code | Meaning | What to do |
|------|---------|------------|
| 2 | Not authenticated / session expired | Tell the user a Chrome window will open for Google login, then run `auth_manager.py reauth` |
| 3 | `.venv` missing or out of date | **Ask the user first**, then run `setup_environment.py` (pip-installs into the skill's own `.venv`; no conda env is touched) |

## Workflow

1. **Ask:** `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --question "..." [--notebook-id ID | --notebook-url URL]`
   - Without either flag the active notebook is used.
   - On exit 2, authenticate (below) and retry once.
2. **Follow up only if needed.** Every answer ends with a short note reminding you that the next question starts a new chat. If the answer leaves a real gap in the user's request, ask one self-contained follow-up that restates the context. Stop after at most 2 follow-ups; quotas are limited.
3. **Synthesize** the answers for the user, keeping NotebookLM's citations where useful.

## Authentication

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py status    # offline check of saved session
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py validate  # live check (headless)
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py setup     # visible browser, user signs in
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py auth_manager.py reauth    # clear profile + setup
```

Setup and reauth open a visible Chrome window and wait up to 10 minutes for the user to sign in. Tell the user before running them. Never try to fill in credentials yourself.

## Notebook library

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py list
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py search --query QUERY
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py activate --id ID
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py remove --id ID
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py stats
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py notebook_manager.py add \
  --url URL --name NAME --description DESC --topics "t1,t2" [--use-cases "..."] [--tags "..."]
```

IDs are generated from the name as shell-safe slugs (`a-z0-9-`).

**Adding a notebook without details from the user:** don't invent a description. Ask the notebook about itself first, then add it with what it says:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py ask_question.py --notebook-url URL \
  --question "Briefly: what sources does this notebook contain and what topics do they cover?"
```

## Troubleshooting

| Problem | Action |
|---------|--------|
| Exit 2 | `auth_manager.py reauth` (visible browser) |
| Exit 3 | Ask user, then `setup_environment.py` (`--recreate` if the venv's base Python was removed) |
| "Could not find the chat input" / "No answer" | The UI likely changed. A screenshot and DOM dump are saved in `${CLAUDE_SKILL_DIR}/data/debug/`; inspect them, or rerun with `--show-browser` |
| Google says "browser may not be secure" | Run `reauth`; if it persists, see `references/troubleshooting.md` |
| Browser profile corrupted | `cleanup_manager.py --confirm --force --preserve-library`, then `auth_manager.py setup` |

## Configuration

Optional `${CLAUDE_SKILL_DIR}/.env` (environment variables take precedence):

```env
HEADLESS=true              # false = always show the browser
QUERY_TIMEOUT_SECONDS=180  # max wait for an answer
TYPING_DELAY_MS_MIN=15     # per-character typing delay
TYPING_DELAY_MS_MAX=45
DEFAULT_NOTEBOOK_ID=       # used when no --notebook-id/--notebook-url is given; overrides the active notebook
```

## Data

All under `${CLAUDE_SKILL_DIR}/data/` (git-ignored, never commit): `library.json`, `auth_info.json`, `browser_state/` (Chrome profile and `state.json` cookies), `debug/` (failure snapshots).

## Limitations

- Automates the web UI (no official consumer API), so Google UI changes can break selectors in `scripts/config.py`.
- Daily chat quotas depend on the user's Google plan.
- Sources must be added to the notebook in the web UI.
- A few seconds of browser startup per question.

More detail: `references/api_reference.md`, `references/troubleshooting.md`, `references/usage_patterns.md`.
