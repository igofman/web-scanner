"""Screenshot extractor using Playwright."""

from pathlib import Path

import structlog
from playwright.async_api import async_playwright, Browser, Page

from ..config import settings
from ..models import CrawledPage, PageStatus
from .base import BaseExtractor

logger = structlog.get_logger()


class ScreenshotExtractor(BaseExtractor):
    """Captures screenshots of web pages using Playwright."""

    def __init__(self, output_dir: Path):
        super().__init__(output_dir / "screenshots")
        self._browser: Browser | None = None
        self._playwright = None

    async def start(self) -> None:
        """Initialize the browser."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            logger.info("Browser started for screenshots")

    async def stop(self) -> None:
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            logger.info("Browser stopped")

    async def _capture_screenshot(self, page: Page, url: str, filepath: Path) -> bool:
        """Capture a screenshot of a single page."""
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait a bit for any lazy-loaded content
            await page.wait_for_timeout(1000)

            await page.screenshot(
                path=str(filepath),
                full_page=settings.screenshot_full_page,
            )

            return True
        except Exception as e:
            logger.warning("Screenshot capture failed", url=url, error=str(e))
            return False

    async def extract(self, page: CrawledPage) -> Path | None:
        """Capture screenshot of the page."""
        if page.status != PageStatus.SUCCESS:
            logger.debug("Skipping screenshot", url=page.url, status=page.status)
            return None

        # Ensure browser is started
        await self.start()

        filename = self._url_to_filename(page.url, "png")
        filepath = self.output_dir / filename

        try:
            browser_page = await self._browser.new_page(
                viewport={
                    "width": settings.screenshot_width,
                    "height": settings.screenshot_height,
                }
            )

            try:
                success = await self._capture_screenshot(browser_page, page.url, filepath)

                if success:
                    logger.info("Captured screenshot", url=page.url, path=str(filepath))
                    return filepath
                return None

            finally:
                await browser_page.close()

        except Exception as e:
            logger.error("Failed to capture screenshot", url=page.url, error=str(e))
            return None

    async def extract_batch(self, pages: list[CrawledPage]) -> dict[str, Path | None]:
        """Extract screenshots for multiple pages efficiently."""
        await self.start()

        results = {}
        for page in pages:
            results[page.url] = await self.extract(page)

        return results
