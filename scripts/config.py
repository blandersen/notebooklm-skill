"""
Configuration for NotebookLM Skill
Centralizes constants, selectors, and paths
"""

import os
import re
from pathlib import Path

# Paths
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILE_DIR = BROWSER_STATE_DIR / "browser_profile"
STATE_FILE = BROWSER_STATE_DIR / "state.json"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"
LIBRARY_FILE = DATA_DIR / "library.json"

# Optional .env in the skill dir; real environment variables take precedence
try:
    from dotenv import load_dotenv
    load_dotenv(SKILL_DIR / ".env", override=False)
except ImportError:
    pass


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# NotebookLM was renamed Gemini Notebook (July 2026) and moved to notebook.google.com.
# notebooklm.google.com still 301-redirects there, so both hosts are accepted.
APP_HOME_URL = "https://notebook.google.com/"
APP_HOSTS = ("notebook.google.com", "notebooklm.google.com")
APP_URL_PATTERN = re.compile(r"^https://(notebook|notebooklm)\.google\.com/")
NOTEBOOK_URL_PATTERN = re.compile(
    r"^https://(?:notebook|notebooklm)\.google\.com/notebook/([A-Za-z0-9_-]+)"
)
LOGIN_HOST = "accounts.google.com"


def normalize_notebook_url(url: str) -> str:
    """Return the canonical notebook.google.com URL, or raise ValueError"""
    match = NOTEBOOK_URL_PATTERN.match(url.strip())
    if not match:
        raise ValueError(
            f"Not a notebook URL: {url!r} "
            "(expected https://notebook.google.com/notebook/<id>)"
        )
    return f"{APP_HOME_URL}notebook/{match.group(1)}"


def is_app_url(url: str) -> bool:
    return bool(APP_URL_PATTERN.match(url))


# Selectors, ordered by preference. Verified against the live UI on 2026-10-16.
QUERY_INPUT_SELECTORS = [
    "textarea.query-box-input",
    'textarea[aria-label="Query box"]',
    'textarea[aria-label="Input for queries"]',
    'textarea[aria-label="Feld für Anfragen"]',
]

# Chat structure (live UI, 2026-10): each Q&A is a .chat-message-pair holding a
# from-user bubble and a to-user bubble. Notebooks keep chat history across sessions.
PAIR_SELECTOR = ".chat-message-pair"
USER_TEXT_SELECTOR = ".from-user-container .message-text-content"
ANSWER_TEXT_SELECTOR = ".to-user-container .message-text-content"
# The copy button is only rendered once an answer has finished
ANSWER_DONE_SELECTOR = ".to-user-container .xap-copy-to-clipboard"
# Collapsible "Thoughts" panel prepended to answers since the June 2026 update
THOUGHTS_SELECTOR = "thinking-chain-view"
CITATION_SELECTOR = ".citation-marker"

# Fallback when the pair structure is not found
RESPONSE_SELECTORS = [
    ANSWER_TEXT_SELECTOR,
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
]

THINKING_SELECTORS = [
    "div.thinking-message",
]

# Promo / "what's new" dialogs that overlay the chat and block clicks
DIALOG_SELECTOR = "mat-dialog-container"
DIALOG_CLOSE_SELECTORS = [
    'mat-dialog-container button[aria-label="Close dialog"]',
    'mat-dialog-container button[aria-label="Close"]',
    'mat-dialog-container button[mat-dialog-close]',
]

# Patchright's own defaults are tuned for undetectability; only add what is needed.
# No custom user agent: a mismatched UA is a strong bot signal on Google login.
BROWSER_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
]

# Headless windows default to 800x600, which gives a cramped layout
HEADLESS_ARGS = ["--window-size=1440,900"]

# Behaviour (overridable via environment or .env)
HEADLESS = _env_bool("HEADLESS", True)
TYPING_DELAY_MS_MIN = int(os.environ.get("TYPING_DELAY_MS_MIN", "15"))
TYPING_DELAY_MS_MAX = int(os.environ.get("TYPING_DELAY_MS_MAX", "45"))
DEFAULT_NOTEBOOK_ID = os.environ.get("DEFAULT_NOTEBOOK_ID") or None

# Timeouts
LOGIN_TIMEOUT_MINUTES = 10
QUERY_TIMEOUT_SECONDS = int(os.environ.get("QUERY_TIMEOUT_SECONDS", "180"))
PAGE_LOAD_TIMEOUT = 30000
INPUT_WAIT_TIMEOUT = 20000
