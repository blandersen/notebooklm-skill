"""
Browser Utilities for NotebookLM Skill
Handles browser launching, stealth features, and common interactions
"""

import json
import time
import random
from typing import Optional, List

from patchright.sync_api import Playwright, BrowserContext, Page, ElementHandle
from config import (
    BROWSER_PROFILE_DIR, STATE_FILE, BROWSER_ARGS, HEADLESS_ARGS,
    TYPING_DELAY_MS_MIN, TYPING_DELAY_MS_MAX,
    DIALOG_SELECTOR, DIALOG_CLOSE_SELECTORS,
)

# Above this length, typing char-by-char is too slow; fill the box instead
MAX_TYPED_CHARS = 400

# Never resolved: requests to it are fulfilled locally by a route
UA_PROBE_URL = "https://ua-probe.invalid/"


class BrowserFactory:
    """Factory for creating configured browser contexts"""

    @staticmethod
    def launch_persistent_context(
        playwright: Playwright,
        headless: bool = True,
        user_data_dir: str = str(BROWSER_PROFILE_DIR)
    ) -> BrowserContext:
        """
        Launch real Chrome on the skill's persistent profile.
        Follows patchright's recommended config: channel=chrome, no_viewport,
        no custom user agent or headers.
        """
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=headless,
            no_viewport=True,
            args=BROWSER_ARGS + (HEADLESS_ARGS if headless else []),
        )

        # Playwright bug #36139: session cookies (expires=-1) are not restored
        # from user_data_dir, so re-inject them from the saved storage state
        BrowserFactory._inject_cookies(context)

        return context

    @staticmethod
    def new_page(context: BrowserContext, headless: bool) -> Page:
        """Open a page; in headless mode, strip 'HeadlessChrome' from the UA"""
        page = context.pages[0] if context.pages else context.new_page()
        if headless:
            BrowserFactory._mask_headless_user_agent(context, page)
        return page

    @staticmethod
    def _mask_headless_user_agent(context: BrowserContext, page: Page):
        """Headless Chrome advertises itself in the UA and client hints; rewrite both"""
        try:
            ua = page.evaluate("navigator.userAgent")
            if "HeadlessChrome" not in ua:
                return
            override = {"userAgent": ua.replace("HeadlessChrome", "Chrome")}

            # userAgentData only exists in secure contexts; serve a blank https page
            # locally so the real client hints can be read without any network request
            page.route(UA_PROBE_URL, lambda route: route.fulfill(status=200, content_type="text/html", body=""))
            page.goto(UA_PROBE_URL)
            page.unroute(UA_PROBE_URL)
            hints = page.evaluate("""async () => {
                const d = navigator.userAgentData;
                if (!d) return null;
                const h = await d.getHighEntropyValues(
                    ['architecture', 'bitness', 'fullVersionList', 'model',
                     'platformVersion', 'uaFullVersion', 'wow64']);
                return {...h, brands: d.brands, mobile: d.mobile, platform: d.platform};
            }""")
            if hints:
                def fix(brands):
                    return [
                        {"brand": "Google Chrome" if b["brand"] == "HeadlessChrome" else b["brand"],
                         "version": b["version"]}
                        for b in brands
                    ]
                override["userAgentMetadata"] = {
                    "brands": fix(hints["brands"]),
                    "fullVersionList": fix(hints.get("fullVersionList", [])),
                    "fullVersion": hints.get("uaFullVersion", ""),
                    "platform": hints["platform"],
                    "platformVersion": hints.get("platformVersion", ""),
                    "architecture": hints.get("architecture", ""),
                    "model": hints.get("model", ""),
                    "mobile": hints["mobile"],
                    "bitness": hints.get("bitness", ""),
                    "wow64": hints.get("wow64", False),
                }

            cdp = context.new_cdp_session(page)
            cdp.send("Network.setUserAgentOverride", override)
        except Exception as e:
            print(f"  ⚠️ Could not mask headless user agent: {e}")

    @staticmethod
    def _inject_cookies(context: BrowserContext):
        """Inject cookies from state.json if available"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                if state.get('cookies'):
                    context.add_cookies(state['cookies'])
            except Exception as e:
                print(f"  ⚠️ Could not load state.json: {e}")


class StealthUtils:
    """Human-like interaction utilities"""

    @staticmethod
    def random_delay(min_ms: int = 100, max_ms: int = 500):
        """Add random delay"""
        time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

    @staticmethod
    def find_first_visible(page: Page, selectors: List[str], timeout_ms: int) -> Optional[ElementHandle]:
        """Poll all selectors until one is visible; return its element"""
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element and element.is_visible():
                        return element
                except Exception:
                    continue
            time.sleep(0.25)
        return None

    @staticmethod
    def dismiss_dialogs(page: Page, max_dialogs: int = 3) -> int:
        """Close overlay dialogs (promos, announcements); returns how many were closed"""
        closed = 0
        for _ in range(max_dialogs):
            dialog = page.query_selector(DIALOG_SELECTOR)
            if not dialog or not dialog.is_visible():
                break
            button = StealthUtils.find_first_visible(page, DIALOG_CLOSE_SELECTORS, 1000)
            if button:
                button.click()
            else:
                page.keyboard.press("Escape")
            try:
                dialog.wait_for_element_state("hidden", timeout=3000)
            except Exception:
                break
            closed += 1
        return closed

    @staticmethod
    def human_type(page: Page, element: ElementHandle, text: str):
        """Type into an element with human-like per-character delays"""
        # A newline would press Enter and submit early
        text = " ".join(text.splitlines())

        element.click()
        StealthUtils.random_delay(100, 300)

        if len(text) > MAX_TYPED_CHARS:
            element.fill(text)
            return

        for char in text:
            page.keyboard.type(char, delay=random.uniform(TYPING_DELAY_MS_MIN, TYPING_DELAY_MS_MAX))
            if random.random() < 0.03:
                time.sleep(random.uniform(0.1, 0.3))
