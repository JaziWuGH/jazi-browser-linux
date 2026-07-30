"""
Browser lifecycle management.

Handles:
- Launching Chromium with persistent profile or system Chrome
- Chrome data migration on first run
- Browser health monitoring
"""

import shutil
import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext


DEFAULT_PROFILE_DIR = Path.home() / ".jazi" / "profile"
CHROME_PROFILE_DIR = Path.home() / ".config" / "google-chrome"


class BrowserManager:
    """Manages the Playwright Chromium browser lifecycle."""

    def __init__(
        self,
        profile_dir: Optional[Path] = None,
        headless: bool = False,
        import_chrome: bool = True,
        use_system_chrome: bool = False,
    ):
        self.profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self.headless = headless
        self.import_chrome = import_chrome
        self.use_system_chrome = use_system_chrome
        self._playwright = None
        self._browser_obj: Optional[Browser] = None  # Always a Browser (can create contexts)
        self._default_context: Optional[BrowserContext] = None
        self._ready = False

    @property
    def browser(self) -> Browser:
        """The Browser object — can create new BrowserContexts."""
        if not self._browser_obj:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._browser_obj

    @property
    def default_context(self) -> BrowserContext:
        """The default BrowserContext — inherits Chrome profile."""
        if not self._default_context:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._default_context

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def start(self):
        """Launch the browser."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # Migrate Chrome data on first run
        if self.import_chrome and not self._has_profile_data():
            await self._migrate_from_chrome()

        self._playwright = await async_playwright().start()

        common_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=TranslateUI",
        ]

        if self.use_system_chrome:
            # Use system-installed Chrome
            self._browser_obj = await self._playwright.chromium.launch(
                channel="chrome",
                headless=self.headless,
                args=common_args,
            )
            self._default_context = await self._browser_obj.new_context(
                viewport={"width": 1280, "height": 800},
                permissions=["clipboard-read", "clipboard-write"],
            )
        else:
            # Use Playwright's bundled Chromium with persistent profile
            persistent_ctx = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                args=common_args,
                permissions=["clipboard-read", "clipboard-write"],
                viewport={"width": 1280, "height": 800},
            )
            # The persistent context IS the default context
            self._default_context = persistent_ctx
            # Get the Browser object from the context (for creating new contexts)
            self._browser_obj = persistent_ctx.browser

        self._ready = True

    async def stop(self):
        """Gracefully shut down the browser."""
        self._ready = False
        if self._browser_obj:
            await self._browser_obj.close()
            self._browser_obj = None
            self._default_context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _has_profile_data(self) -> bool:
        """Check if the profile directory already has browser data."""
        pref_file = self.profile_dir / "Default" / "Preferences"
        cookies_file = self.profile_dir / "Default" / "Cookies"
        return pref_file.exists() or cookies_file.exists()

    async def _migrate_from_chrome(self):
        """Copy Chrome profile data into Jazi profile directory."""
        chrome_default = CHROME_PROFILE_DIR / "Default"
        if not chrome_default.exists():
            return

        jazi_default = self.profile_dir / "Default"
        jazi_default.mkdir(parents=True, exist_ok=True)

        to_copy = [
            "Cookies", "Cookies-journal",
            "Login Data", "Login Data-journal",
            "Preferences",
            "Web Data", "Web Data-journal",
        ]
        copied = 0
        for fname in to_copy:
            src = chrome_default / fname
            dst = jazi_default / fname
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
                copied += 1

        if copied:
            import logging
            logging.info(f"Migrated {copied} files from Chrome profile")


# Global singleton
_manager: Optional[BrowserManager] = None


async def get_manager(
    profile_dir: Optional[Path] = None,
    headless: bool = False,
    use_system_chrome: bool = True,
) -> BrowserManager:
    """Get or create the global BrowserManager singleton.

    Defaults to using system Chrome to avoid downloading Playwright's Chromium.
    """
    global _manager
    if _manager is None or not _manager.is_ready:
        _manager = BrowserManager(
            profile_dir=profile_dir,
            headless=headless,
            use_system_chrome=use_system_chrome,
        )
        await _manager.start()
    return _manager


async def shutdown():
    """Shut down the global browser manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
