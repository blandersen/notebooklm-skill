# NotebookLM Skill Usage Patterns

Patterns for using the skill well. All commands go through the wrapper with its absolute path, from any working directory:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/run.py <script>.py [args]
```

Below, `RUN` stands for `python3 ${CLAUDE_SKILL_DIR}/scripts/run.py`.

## 1. First use

```bash
RUN auth_manager.py status
```

- Exit 3 from `run.py`: the `.venv` is missing or outdated. Ask the user, then `RUN setup_environment.py`.
- "Authenticated: No": tell the user a Chrome window will open for Google sign-in, then `RUN auth_manager.py setup`. Never type credentials for them.

## 2. Adding a notebook

The user shares a link (`https://notebook.google.com/notebook/...` or an old `notebooklm.google.com` link; both work).

If the user gave a name and description, add it directly. Otherwise ask the notebook about itself, and use its answer. Don't invent a description.

```bash
RUN ask_question.py --notebook-url URL \
  --question "Briefly: what sources does this notebook contain and what topics do they cover?"

RUN notebook_manager.py add --url URL \
  --name "React Docs" \
  --description "Official React documentation, hooks and server components" \
  --topics "react,hooks,components"
```

The ID is a slug of the name (`react-docs`). Adding a URL that is already in the library fails with the existing ID, which you can just use.

## 3. Asking well

Each question is answered in a fresh browser session, and earlier turns may not be used as context. Write each question so it stands alone:

- Name the subject explicitly instead of "it" or "that".
- Combine related sub-questions into one question when they share context.
- Ask for the structure you need ("list the parameters with types and defaults").
- Include version numbers, error messages or constraints from the user's task.

Bad: `"What about error handling?"`
Good: `"In the n8n Gmail trigger node, how are authentication and rate-limit errors reported, and how should a workflow retry them?"`

## 4. Follow-ups

Every answer ends with:

```
[Note to assistant: if this answer leaves a gap in the user's request, ask one self-contained follow-up that restates the needed context; otherwise answer the user.]
```

1. Compare the answer against what the user actually asked.
2. If a specific gap remains, ask **one** self-contained follow-up that restates the context.
3. Stop after at most **2** follow-ups per user request. Quotas are limited and each query takes ~20-25 s.
4. Synthesize the answers for the user, keeping citations (`[n]`) where useful. Say so if the notebook doesn't cover something rather than filling the gap from general knowledge.

## 5. Multiple notebooks

Pass `--notebook-id` per call instead of switching the active notebook back and forth:

```bash
RUN ask_question.py --notebook-id backend-api --question "..."
RUN ask_question.py --notebook-id frontend-docs --question "..."
```

`notebook_manager.py search --query backend` finds candidates by name, description, topics, tags and use cases. Use `activate` only when the user wants a new default.

Run queries one after another, never in parallel: they share one Chrome profile.

## 6. Handling exit codes

| Exit | Do |
|------|----|
| 0 | Use the answer |
| 1 | Read the message. "No answer" or "Could not find the chat input": look at `${CLAUDE_SKILL_DIR}/data/debug/`, retry once, or retry with `--show-browser`. Don't retry repeatedly. |
| 2 | Tell the user a browser will open, `RUN auth_manager.py reauth`, then retry the question once |
| 3 | Ask the user, `RUN setup_environment.py`, then retry |

## 7. Chat history

Every question the skill asks is saved to the notebook's chat history in the user's account, visible in the web UI. Mention this if the user cares about a tidy history. The skill does not delete history and only returns the answer to the question it just asked.

## 8. Several questions in a script

```bash
for q in "First self-contained question" "Second self-contained question"; do
  python3 ~/.claude/skills/notebooklm/scripts/run.py ask_question.py \
    --notebook-id api-docs --question "$q" || break
done
```

Sequential only. Stop on a non-zero exit instead of hammering a failing setup.

## 9. Library hygiene

- Use descriptive names (they become IDs) and real descriptions and topics so `search` finds the right notebook.
- `notebook_manager.py stats` shows the most-used notebook; `use_count` and `last_used` are updated after each successful query.
- `remove --id ID` removes the entry from the library only, not the notebook from Google.

## Quick reference

```bash
RUN ask_question.py --question "..." [--notebook-id ID | --notebook-url URL] [--show-browser]
RUN notebook_manager.py {list, search --query Q, activate --id ID, remove --id ID, stats}
RUN notebook_manager.py add --url URL --name NAME --description DESC --topics "a,b"
RUN auth_manager.py {status, validate, setup, reauth, clear}
RUN setup_environment.py [--check] [--recreate]      # ask the user first
RUN cleanup_manager.py [--confirm] [--preserve-library] [--force]
```
