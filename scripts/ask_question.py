#!/usr/bin/env python3
"""
NotebookLM (Gemini Notebook) Question Interface
Opens the notebook in a fresh browser session, asks one question, returns the answer.

Hybrid auth approach:
- Persistent browser profile (user_data_dir) for fingerprint consistency
- Cookie injection from state.json for session cookies (Playwright bug #36139)
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from patchright.sync_api import sync_playwright, Page

sys.path.insert(0, str(Path(__file__).parent))

from auth_manager import AuthManager
from notebook_manager import NotebookLibrary
from config import (
    QUERY_INPUT_SELECTORS, RESPONSE_SELECTORS, THINKING_SELECTORS,
    PAIR_SELECTOR, USER_TEXT_SELECTOR, ANSWER_TEXT_SELECTOR, ANSWER_DONE_SELECTOR,
    THOUGHTS_SELECTOR, CITATION_SELECTOR,
    HEADLESS, DEFAULT_NOTEBOOK_ID, QUERY_TIMEOUT_SECONDS, PAGE_LOAD_TIMEOUT,
    INPUT_WAIT_TIMEOUT, LOGIN_HOST, DATA_DIR, NOTEBOOK_URL_PATTERN, normalize_notebook_url,
)
from browser_utils import BrowserFactory, StealthUtils

RUN = f"python3 {Path(__file__).resolve().parent / 'run.py'}"
DEBUG_DIR = DATA_DIR / "debug"

# Appended to every answer. The notebook's chat history persists between calls, but
# whether earlier turns are used as context is not guaranteed, so follow-ups restate it.
FOLLOW_UP_REMINDER = (
    "\n\n[Note to assistant: if this answer leaves a gap in the user's request, ask one "
    "self-contained follow-up that restates the needed context; otherwise answer the user.]"
)

EXIT_OK, EXIT_FAILED, EXIT_AUTH = 0, 1, 2


class AuthExpired(Exception):
    pass


def _responses(page: Page) -> Tuple[int, Optional[str]]:
    """Fallback: count of answer bubbles and text of the newest"""
    for selector in RESPONSE_SELECTORS:
        try:
            elements = page.query_selector_all(selector)
        except Exception:
            continue
        if elements:
            try:
                return len(elements), elements[-1].inner_text().strip()
            except Exception:
                return len(elements), None
    return 0, None


# Reads the newest Q&A pair; the answer text excludes the Thoughts panel and
# renders citation markers as [n] and math as $LaTeX$. Works on a clone so the live DOM is untouched.
LAST_PAIR_JS = """([pairSel, userSel, answerSel, doneSel, thoughtsSel, citeSel]) => {
    const pairs = document.querySelectorAll(pairSel);
    if (!pairs.length) return null;
    const pair = pairs[pairs.length - 1];
    const user = pair.querySelector(userSel);
    const answer = pair.querySelector(answerSel);
    let text = null;
    if (answer) {
        const clone = answer.cloneNode(true);
        clone.querySelectorAll(thoughtsSel).forEach(e => e.remove());
        clone.querySelectorAll(citeSel).forEach(e => {
            const n = e.textContent.trim();
            e.replaceWith(/^\\d+$/.test(n) ? ` [${n}]` : '');
        });
        clone.querySelectorAll('mat-icon').forEach(e => e.remove());
        // KaTeX keeps the LaTeX source in data-math; emit it instead of the glyph soup
        clone.querySelectorAll('[data-math]').forEach(e => e.replaceWith(`$${e.dataset.math}$`));
        clone.querySelectorAll('sup').forEach(e => e.prepend('^'));
        clone.querySelectorAll('sub').forEach(e => e.prepend('_'));
        // Detached nodes have no layout, so add line breaks for block elements by hand
        clone.querySelectorAll('div, p, li, h1, h2, h3, h4, tr, br').forEach(e => e.append('\\n'));
        clone.querySelectorAll('li').forEach(e => e.prepend('- '));
        text = clone.textContent.replace(/[ \\t]+\\n/g, '\\n').replace(/\\n{3,}/g, '\\n\\n').trim();
    }
    return {
        count: pairs.length,
        user: user ? user.innerText.trim() : null,
        answer: text,
        done: !!pair.querySelector(doneSel),
    };
}"""


def _last_pair(page: Page) -> Optional[dict]:
    try:
        return page.evaluate(LAST_PAIR_JS, [
            PAIR_SELECTOR, USER_TEXT_SELECTOR, ANSWER_TEXT_SELECTOR,
            ANSWER_DONE_SELECTOR, THOUGHTS_SELECTOR, CITATION_SELECTOR,
        ])
    except Exception:
        return None


def _normalize(text: str) -> str:
    """Compare questions loosely: the UI may re-render markdown or whitespace"""
    return re.sub(r"\W+", " ", text).strip().lower()


def _is_thinking(page: Page) -> bool:
    for selector in THINKING_SELECTORS:
        try:
            element = page.query_selector(selector)
            if element and element.is_visible():
                return True
        except Exception:
            continue
    return False


def _save_debug(page: Optional[Page], reason: str):
    """Keep a screenshot and DOM dump so selector drift can be diagnosed"""
    if page is None:
        return
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        page.screenshot(path=str(DEBUG_DIR / f"{stamp}-{reason}.png"), full_page=True)
        (DEBUG_DIR / f"{stamp}-{reason}.html").write_text(page.content())
        print(f"  🧪 Saved debug snapshot to {DEBUG_DIR}/{stamp}-{reason}.*")
    except Exception as e:
        print(f"  ⚠️ Could not save debug snapshot: {e}")


def _wait_for_answer(page: Page, question: str, baseline_pairs: int,
                     baseline_count: int, baseline_text: Optional[str]) -> Optional[str]:
    """
    Wait for the answer to our question, then for its text to settle.
    Notebooks keep chat history, so the answer must be in a pair added after
    submitting whose user bubble holds our question.
    """
    deadline = time.time() + QUERY_TIMEOUT_SECONDS
    asked = _normalize(question)[:200]
    last_text = None
    stable_polls = 0

    while time.time() < deadline:
        time.sleep(1)
        if _is_thinking(page):
            stable_polls = 0
            continue

        pair = _last_pair(page)
        if pair is not None:
            ours = (pair["count"] > baseline_pairs and pair["user"]
                    and _normalize(pair["user"])[:200] == asked)
            text = pair["answer"] if ours else None
            done = pair["done"]
        else:
            # Fallback for an unknown layout: any bubble that was not there before
            count, text = _responses(page)
            if not (count > baseline_count or (text and text != baseline_text)):
                text = None
            done = False

        if not text:
            stable_polls = 0
            continue
        if text == last_text:
            stable_polls += 1
            # Finished marker plus a short settle, or a longer settle without it
            if (done and stable_polls >= 2) or stable_polls >= 6:
                return text
        else:
            stable_polls = 0
            last_text = text

    return None


def ask_notebooklm(question: str, notebook_url: str, headless: bool = True) -> Optional[str]:
    """
    Ask a question to a notebook

    Raises:
        AuthExpired: when Google redirects to the login page
    """
    auth = AuthManager()
    if not auth.is_authenticated():
        raise AuthExpired("No saved Google session")

    print(f"💬 Asking: {question}")
    print(f"📚 Notebook: {notebook_url}")

    playwright = None
    context = None
    page = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=headless)
        page = BrowserFactory.new_page(context, headless)

        print("  🌐 Opening notebook...")
        page.goto(notebook_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        if LOGIN_HOST in page.url:
            raise AuthExpired("Redirected to Google login")

        print("  ⏳ Waiting for query input...")
        query_element = StealthUtils.find_first_visible(page, QUERY_INPUT_SELECTORS, INPUT_WAIT_TIMEOUT)
        if LOGIN_HOST in page.url:
            raise AuthExpired("Redirected to Google login")
        if not query_element:
            print("  ❌ Could not find the chat input (UI may have changed)")
            _save_debug(page, "no-input")
            return None

        # Let restored chat history and any promo dialogs render first
        StealthUtils.random_delay(1000, 1500)
        if StealthUtils.dismiss_dialogs(page):
            print("  ✓ Dismissed overlay dialog")
        baseline_count, baseline_text = _responses(page)
        baseline_pair = _last_pair(page)
        baseline_pairs = baseline_pair["count"] if baseline_pair else 0

        # A missing or unshared notebook briefly renders, then redirects to the home page
        if not NOTEBOOK_URL_PATTERN.match(page.url):
            print("  ❌ Notebook not found, or this Google account has no access to it")
            return None

        # Re-query: the element found earlier may have been re-rendered
        query_element = StealthUtils.find_first_visible(page, QUERY_INPUT_SELECTORS, INPUT_WAIT_TIMEOUT)
        if not query_element:
            print("  ❌ Chat input disappeared")
            _save_debug(page, "no-input")
            return None

        print("  ⏳ Typing question...")
        StealthUtils.human_type(page, query_element, question)
        StealthUtils.random_delay(200, 500)

        print("  📤 Submitting...")
        page.keyboard.press("Enter")

        print("  ⏳ Waiting for answer...")
        answer = _wait_for_answer(page, question, baseline_pairs, baseline_count, baseline_text)
        if not answer:
            print(f"  ❌ No answer within {QUERY_TIMEOUT_SECONDS}s")
            _save_debug(page, "no-answer")
            return None

        # Persist rotated session cookies so the login lasts longer
        try:
            auth._save_browser_state(context)
        except Exception:
            pass

        print("  ✅ Got answer!")
        return answer

    except AuthExpired:
        raise
    except Exception as e:
        print(f"  ❌ Error: {e}")
        _save_debug(page, "error")
        return None

    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description='Ask a NotebookLM / Gemini Notebook a question')

    parser.add_argument('--question', required=True, help='Question to ask')
    parser.add_argument('--notebook-url', help='Notebook URL')
    parser.add_argument('--notebook-id', help='Notebook ID from library')
    parser.add_argument('--show-browser', action='store_true', help='Show browser')

    args = parser.parse_args()

    library = NotebookLibrary()
    notebook_url = args.notebook_url
    notebook_id = args.notebook_id or (None if notebook_url else DEFAULT_NOTEBOOK_ID)

    if not notebook_url and notebook_id:
        notebook = library.get_notebook(notebook_id)
        if not notebook:
            print(f"❌ Notebook '{notebook_id}' not found. List with: {RUN} notebook_manager.py list")
            return EXIT_FAILED
        notebook_url = notebook['url']
        notebook_id = notebook['id']

    if not notebook_url:
        active = library.get_active_notebook()
        if active:
            notebook_url = active['url']
            notebook_id = active['id']
            print(f"📚 Using active notebook: {active['name']}")
        else:
            notebooks = library.list_notebooks()
            if notebooks:
                print("\n📚 Available notebooks:")
                for nb in notebooks:
                    print(f"  {nb['id']}: {nb['name']}")
                print(f"\nSpecify with --notebook-id or set one active: {RUN} notebook_manager.py activate --id ID")
            else:
                print(f"❌ No notebooks in library. Add one: {RUN} notebook_manager.py add --url URL --name NAME --description DESC --topics TOPICS")
            return EXIT_FAILED

    try:
        notebook_url = normalize_notebook_url(notebook_url)
    except ValueError as e:
        print(f"❌ {e}")
        return EXIT_FAILED

    if not notebook_id:
        notebook_id = next((nb['id'] for nb in library.list_notebooks() if nb['url'] == notebook_url), None)

    try:
        answer = ask_notebooklm(
            question=args.question,
            notebook_url=notebook_url,
            headless=HEADLESS and not args.show_browser,
        )
    except AuthExpired as e:
        print(f"\n🔐 Not authenticated ({e}).")
        print(f"   Ask the user to run (a browser window opens for Google login): {RUN} auth_manager.py reauth")
        return EXIT_AUTH

    if not answer:
        print("\n❌ Failed to get answer")
        return EXIT_FAILED

    if notebook_id:
        try:
            library.increment_use_count(notebook_id)
        except Exception:
            pass

    print("\n" + "=" * 60)
    print(f"Question: {args.question}")
    print("=" * 60)
    print()
    print(answer + FOLLOW_UP_REMINDER)
    print()
    print("=" * 60)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
