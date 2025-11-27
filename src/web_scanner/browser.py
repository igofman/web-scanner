"""Browser manager for Playwright-based web scraping."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)

from .config import settings

logger = structlog.get_logger()


class BrowserManager:
    """Manages Playwright browser lifecycle and provides page contexts."""

    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        """Initialize the browser."""
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        )

        # Create a persistent context with common settings
        self._context = await self._browser.new_context(
            viewport={
                "width": settings.screenshot_width,
                "height": settings.screenshot_height,
            },
            user_agent=settings.user_agent,
            ignore_https_errors=True,
            java_script_enabled=True,
            bypass_csp=True,  # Bypass Content Security Policy for better scraping
        )

        logger.info(
            "Browser started",
            viewport=f"{settings.screenshot_width}x{settings.screenshot_height}",
        )

    async def stop(self) -> None:
        """Close the browser and cleanup resources."""
        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Browser stopped")

    @asynccontextmanager
    async def new_page(self) -> AsyncGenerator[Page, None]:
        """Create a new page in the browser context."""
        if self._context is None:
            await self.start()

        page = await self._context.new_page()
        try:
            yield page
        finally:
            await page.close()

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


class SmartPageLoader:
    """Handles intelligent page loading with JavaScript execution."""

    def __init__(
        self,
        page: Page,
        wait_for_timeout: int = 3000,
        wait_for_selector: str | None = None,
    ):
        self.page = page
        self.wait_for_timeout = wait_for_timeout
        self.wait_for_selector = wait_for_selector

    async def goto(
        self,
        url: str,
        timeout: int = 30000,
        wait_until: str = "networkidle",
    ) -> bool:
        """
        Navigate to URL with smart waiting for JavaScript content.

        Args:
            url: The URL to navigate to
            timeout: Maximum time to wait in milliseconds
            wait_until: When to consider navigation complete
                       Options: 'load', 'domcontentloaded', 'networkidle', 'commit'

        Returns:
            True if page loaded successfully, False otherwise
        """
        try:
            # Navigate to the page
            response = await self.page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout,
            )

            if response is None:
                logger.warning("No response received", url=url)
                return False

            # Check for successful response
            if response.status >= 400:
                logger.warning(
                    "HTTP error response",
                    url=url,
                    status=response.status,
                )
                return False

            # Wait for additional dynamic content
            await self._wait_for_dynamic_content()

            return True

        except PlaywrightTimeout:
            logger.warning("Page load timeout", url=url, timeout=timeout)
            return False
        except Exception as e:
            logger.warning("Page load failed", url=url, error=str(e))
            return False

    async def _wait_for_dynamic_content(self) -> None:
        """Wait for dynamic JavaScript content to render."""
        # Wait for any specific selector if provided
        if self.wait_for_selector:
            try:
                await self.page.wait_for_selector(
                    self.wait_for_selector,
                    timeout=self.wait_for_timeout,
                )
            except PlaywrightTimeout:
                logger.debug(
                    "Selector not found",
                    selector=self.wait_for_selector,
                )

        # Wait for network to be idle (no requests for 500ms)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeout:
            pass  # Continue even if network doesn't fully idle

        # Additional wait for animations and lazy loading
        await self.page.wait_for_timeout(self.wait_for_timeout)

        # Scroll to trigger lazy-loaded content
        await self._trigger_lazy_loading()

    async def _trigger_lazy_loading(self) -> None:
        """Scroll through the page to trigger lazy-loaded content."""
        try:
            # Get page height
            scroll_height = await self.page.evaluate("document.body.scrollHeight")
            viewport_height = self.page.viewport_size["height"]

            # Scroll incrementally
            current_position = 0
            while current_position < scroll_height:
                current_position += viewport_height // 2
                await self.page.evaluate(f"window.scrollTo(0, {current_position})")
                await self.page.wait_for_timeout(200)

            # Scroll back to top for screenshot
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(500)

        except Exception as e:
            logger.debug("Lazy loading scroll failed", error=str(e))

    async def get_content(self) -> str:
        """Get the fully rendered HTML content."""
        return await self.page.content()

    async def get_text(self) -> str:
        """Extract visible text from the page."""
        return await self.page.evaluate("""
            () => {
                // Remove script, style, and hidden elements
                const elementsToRemove = document.querySelectorAll(
                    'script, style, noscript, [hidden], [aria-hidden="true"]'
                );
                elementsToRemove.forEach(el => el.remove());

                // Get visible text
                return document.body.innerText || document.body.textContent || '';
            }
        """)

    async def get_title(self) -> str | None:
        """Get the page title."""
        return await self.page.title()

    async def get_links(self) -> list[str]:
        """Extract all links from the page."""
        return await self.page.evaluate("""
            () => {
                const links = [];
                const anchors = document.querySelectorAll('a[href]');
                anchors.forEach(a => {
                    const href = a.href;
                    if (href && !href.startsWith('javascript:') &&
                        !href.startsWith('mailto:') && !href.startsWith('tel:')) {
                        links.push(href);
                    }
                });
                return [...new Set(links)];
            }
        """)

    async def capture_screenshot(
        self,
        path: str,
        full_page: bool = True,
    ) -> bool:
        """Capture a screenshot of the page."""
        try:
            await self.page.screenshot(
                path=path,
                full_page=full_page,
                animations="disabled",  # Disable animations for consistent screenshots
            )
            return True
        except Exception as e:
            logger.warning("Screenshot capture failed", path=path, error=str(e))
            return False


async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
):
    """Execute a function with exponential backoff retry."""
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.debug(
                    "Retrying after failure",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)

    raise last_exception
