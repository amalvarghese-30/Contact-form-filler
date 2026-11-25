"""Managed Playwright browser lifecycle for scraping and form filling."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, BrowserContext, async_playwright

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def managed_browser_context(block_assets: bool = False) -> AsyncGenerator[BrowserContext, None]:
    """
    Launch a single Chromium browser + context for a batch or scan,
    applying configured timeouts and guaranteeing clean teardown even on crashes.
    """
    settings = get_settings()
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    browser: Browser | None = None
    context: BrowserContext | None = None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=settings.headless)
            context = await browser.new_context()
            context.set_default_timeout(settings.action_timeout_ms)
            if block_assets:
                async def _abort_heavy(route):
                    if route.request.resource_type in {"image", "media", "font"}:
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route("**/*", _abort_heavy)
            yield context
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception as e:
                    logger.debug(f"Context close warning: {e}")
            if browser is not None:
                try:
                    await browser.close()
                except Exception as e:
                    logger.debug(f"Browser close warning: {e}")
