"""
Page tools — the JavaScript API exposed to AI agents for browser control.

JS-based page control: agents call these tools directly,
and the code runs in the page context in one pass.

Available tools:
    navigate(url)       — Navigate to a URL
    snapshot()          — Get structured page snapshot (interactive elements with @eN refs)
    click(ref)          — Click an interactive element by ref ID (@e1, @e2, ...)
    fill(ref, value)    — Fill an input field by ref ID
    wait(text)          — Wait for specific text to appear on the page
    capture()          — Take a screenshot (returns base64 PNG)
    get_text()          — Get visible text from the page
    eval(js)            — Evaluate arbitrary JavaScript in the page
"""

import base64
from typing import Optional

from playwright.async_api import Page

from .snapshot import snapshot as take_snapshot


async def navigate(page: Page, url: str, timeout: int = 30000) -> dict:
    """Navigate to a URL and return a snapshot."""
    await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
    snap = await take_snapshot(page)
    return {"url": page.url, "snapshot": snap}


async def snapshot(page: Page) -> str:
    """Get a structured snapshot of the current page."""
    return await take_snapshot(page)


async def click(page: Page, ref: str) -> dict:
    """Click an element by its @eN ref ID.

    The ref IDs come from the snapshot output.
    Each interactive element gets a data-jazi-ref attribute for targeting.
    """
    selector = f'[data-jazi-ref="{ref}"]'

    # Verify the element exists
    exists = await page.evaluate(
        f"() => !!document.querySelector('[data-jazi-ref=\"{ref}\"]')"
    )
    if not exists:
        # Try to re-snapshot and give the agent updated refs
        snap = await take_snapshot(page)
        return {
            "error": f"Element {ref} not found on current page. Page may have changed.",
            "current_snapshot": snap,
        }

    try:
        await page.click(selector, timeout=10000)
        # Wait for any navigation or DOM changes
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        snap = await take_snapshot(page)
        return {
            "clicked": ref,
            "url": page.url,
            "snapshot": snap,
        }
    except Exception as e:
        return {"error": f"Click on {ref} failed: {str(e)}"}


async def fill(page: Page, ref: str, value: str) -> dict:
    """Fill an input field by its @eN ref ID."""
    selector = f'[data-jazi-ref="{ref}"]'

    exists = await page.evaluate(
        f"() => !!document.querySelector('[data-jazi-ref=\"{ref}\"]')"
    )
    if not exists:
        snap = await take_snapshot(page)
        return {
            "error": f"Element {ref} not found on current page.",
            "current_snapshot": snap,
        }

    try:
        await page.fill(selector, value, timeout=10000)
        return {"filled": ref, "value": value}
    except Exception as e:
        return {"error": f"Fill on {ref} failed: {str(e)}"}


async def wait_for(page: Page, text: str, timeout: int = 15000) -> dict:
    """Wait for specific text to appear on the page."""
    try:
        await page.wait_for_function(
            f"() => document.body?.innerText?.includes({repr(text)})",
            timeout=timeout,
        )
        snap = await take_snapshot(page)
        return {"found": text, "snapshot": snap}
    except Exception as e:
        return {"error": f"Wait for '{text}' timed out: {str(e)}"}


async def capture(page: Page) -> dict:
    """Take a screenshot, return base64-encoded PNG."""
    try:
        screenshot_bytes = await page.screenshot(type="png", full_page=False)
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        return {"screenshot": b64, "format": "png", "url": page.url}
    except Exception as e:
        return {"error": str(e)}


async def get_text(page: Page, max_chars: int = 5000) -> dict:
    """Extract visible text from the page."""
    try:
        text = await page.evaluate(
            f"() => (document.body?.innerText || '').substring(0, {max_chars})"
        )
        return {"text": text, "url": page.url}
    except Exception as e:
        return {"error": str(e)}


async def eval_js(page: Page, js_code: str) -> dict:
    """Evaluate arbitrary JavaScript in the page context."""
    try:
        result = await page.evaluate(js_code)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}
