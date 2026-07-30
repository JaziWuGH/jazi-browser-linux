"""
Space — isolated browser workspace for AI agents.

Each Space is a Playwright BrowserContext with its own:
- Cookies and storage
- Active page(s)
- Task state

Multiple Spaces can run in parallel without interfering with each other.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)


@dataclass
class Space:
    """An isolated browser workspace for an AI agent."""

    name: str
    context: BrowserContext
    created_at: float = field(default_factory=lambda: __import__("time").time())

    @property
    async def pages(self) -> list[Page]:
        return self.context.pages

    @property
    async def active_page(self) -> Optional[Page]:
        """Get the most recently active page, or create one."""
        pages = self.context.pages
        if pages:
            return pages[-1]
        return await self.context.new_page()

    async def close(self):
        """Close this space and all its pages."""
        try:
            await self.context.close()
        except Exception as e:
            logger.warning(f"Error closing space '{self.name}': {e}")


class SpaceManager:
    """Creates and manages isolated browser Spaces."""

    def __init__(self):
        self._spaces: Dict[str, Space] = {}
        self._default_space: Optional[str] = None

    @property
    def spaces(self) -> dict:
        return self._spaces

    async def create(
        self,
        name: str,
        browser_manager=None,
        inherit_cookies: bool = False,
    ) -> Space:
        """Create a new isolated Space.

        Args:
            name: Unique space name
            browser_manager: BrowserManager instance
            inherit_cookies: If True, copy cookies from the default context
        """
        if name in self._spaces:
            raise ValueError(f"Space '{name}' already exists")

        if browser_manager is None or not browser_manager.is_ready:
            raise RuntimeError("Browser not ready. Start the browser first.")

        browser = browser_manager.browser

        # Create a new isolated context
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            # Each space gets its own storage
            storage_state=None,
        )

        # Inherit cookies from the main profile if requested
        if inherit_cookies:
            try:
                default_pages = browser.pages if hasattr(browser, 'pages') else []
                if default_pages:
                    cookies = await default_pages[0].context.cookies()
                    await context.add_cookies(cookies)
            except Exception as e:
                logger.warning(f"Could not inherit cookies: {e}")

        # Create initial page
        await context.new_page()

        space = Space(name=name, context=context)
        self._spaces[name] = space

        if self._default_space is None:
            self._default_space = name

        logger.info(f"Space '{name}' created")
        return space

    def get(self, name: str) -> Optional[Space]:
        """Get a space by name."""
        return self._spaces.get(name)

    def get_or_default(self, name: Optional[str] = None) -> Space:
        """Get a space by name, or the default space."""
        if name:
            space = self._spaces.get(name)
            if space:
                return space
            raise ValueError(f"Space '{name}' not found")
        if self._default_space:
            return self._spaces[self._default_space]
        raise RuntimeError("No spaces available. Create one first.")

    async def close(self, name: str):
        """Close and remove a space."""
        space = self._spaces.pop(name, None)
        if space:
            await space.close()
            if self._default_space == name:
                # Pick a new default
                self._default_space = next(iter(self._spaces), None)
            logger.info(f"Space '{name}' closed")

    async def close_all(self):
        """Close all spaces."""
        for name in list(self._spaces.keys()):
            await self.close(name)

    def list_spaces(self) -> list[dict]:
        """List all active spaces with metadata."""
        result = []
        for name, space in self._spaces.items():
            # Count pages synchronously (context.pages is a property, no await needed)
            page_count = len(space.context.pages)
            result.append({
                "name": name,
                "is_default": name == self._default_space,
                "page_count": page_count,
            })
        return result

    async def _count_pages(self, space: Space) -> int:
        return len(space.context.pages)
