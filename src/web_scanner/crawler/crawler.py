"""Core web crawler implementation using Playwright for JavaScript support."""

import asyncio
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import structlog
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from ..browser import BrowserManager, SmartPageLoader, retry_with_backoff
from ..config import settings
from ..models import CrawledPage, PageStatus

logger = structlog.get_logger()


class WebCrawler:
    """
    Playwright-based web crawler that discovers and fetches pages.

    Uses a real browser to:
    - Execute JavaScript fully
    - Render dynamic content
    - Capture accurate screenshots
    - Extract links from fully-rendered DOM
    """

    def __init__(
        self,
        base_url: str,
        max_depth: int | None = None,
        max_pages: int | None = None,
        concurrent_requests: int | None = None,
        screenshot_dir: Path | None = None,
        capture_screenshots: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.base_domain = urlparse(base_url).netloc
        self.max_depth = max_depth or settings.max_depth
        self.max_pages = max_pages or settings.max_pages
        self.concurrent_requests = concurrent_requests or settings.concurrent_requests
        self.screenshot_dir = screenshot_dir
        self.capture_screenshots = capture_screenshots

        self.visited_urls: set[str] = set()
        self.crawled_pages: list[CrawledPage] = []
        self.url_queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self._semaphore: asyncio.Semaphore | None = None
        self._browser_manager: BrowserManager | None = None

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL by removing fragments and trailing slashes."""
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.rstrip("/")

    def _is_valid_url(self, url: str) -> bool:
        """Check if a URL should be crawled."""
        try:
            parsed = urlparse(url)

            # Must be same domain
            if parsed.netloc != self.base_domain:
                return False

            # Must be http or https
            if parsed.scheme not in ("http", "https"):
                return False

            # Skip common non-page resources
            skip_extensions = (
                ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
                ".css", ".js", ".xml", ".json", ".zip", ".tar", ".gz",
                ".mp3", ".mp4", ".avi", ".mov", ".webm", ".woff", ".woff2",
                ".ttf", ".eot", ".map",
            )
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in skip_extensions):
                return False

            return True
        except Exception:
            return False

    def _url_to_filename(self, url: str, extension: str) -> str:
        """Convert URL to a safe filename."""
        parsed = urlparse(url)
        path = parsed.path.strip("/") or "index"

        # Replace path separators and special chars
        safe_name = path.replace("/", "_").replace("?", "_").replace("&", "_")

        # Add query hash if present
        if parsed.query:
            import hashlib
            query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
            safe_name = f"{safe_name}_{query_hash}"

        return f"{safe_name}.{extension}"

    def _filter_links(self, links: list[str], current_url: str) -> list[str]:
        """Filter and normalize extracted links."""
        filtered = []
        for link in links:
            # Convert relative URLs to absolute
            absolute_url = urljoin(current_url, link)
            normalized = self._normalize_url(absolute_url)

            if self._is_valid_url(normalized) and normalized not in filtered:
                filtered.append(normalized)

        return filtered

    async def _fetch_page(
        self,
        url: str,
        depth: int,
        page: Page,
    ) -> CrawledPage:
        """Fetch a single page using Playwright and extract its content."""
        start_time = time.time()
        screenshot_path: str | None = None

        try:
            # Create smart page loader
            loader = SmartPageLoader(
                page=page,
                wait_for_timeout=settings.js_wait_timeout,
                wait_for_selector=settings.wait_for_selector,
            )

            # Navigate with retry logic
            async def navigate():
                success = await loader.goto(
                    url,
                    timeout=settings.page_load_timeout,
                    wait_until="networkidle",
                )
                if not success:
                    raise Exception("Navigation failed")
                return success

            try:
                await retry_with_backoff(
                    navigate,
                    max_retries=settings.max_retries,
                    base_delay=1.0,
                )
            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                return CrawledPage(
                    url=url,
                    status=PageStatus.ERROR,
                    depth=depth,
                    error_message=str(e),
                    response_time_ms=response_time,
                )

            response_time = (time.time() - start_time) * 1000

            # Extract content from fully rendered page
            html = await loader.get_content()
            text = await loader.get_text()
            title = await loader.get_title()
            raw_links = await loader.get_links()
            links = self._filter_links(raw_links, url)

            # Capture screenshot if enabled
            if self.capture_screenshots and self.screenshot_dir:
                filename = self._url_to_filename(url, "png")
                screenshot_path = str(self.screenshot_dir / filename)
                screenshot_success = await loader.capture_screenshot(
                    path=screenshot_path,
                    full_page=settings.screenshot_full_page,
                )
                if screenshot_success:
                    logger.info("Captured screenshot", url=url, path=screenshot_path)
                else:
                    screenshot_path = None

            return CrawledPage(
                url=url,
                status=PageStatus.SUCCESS,
                status_code=200,
                content_type="text/html",
                html=html,
                text=text,
                title=title,
                links=links,
                depth=depth,
                response_time_ms=response_time,
                screenshot_path=screenshot_path,
            )

        except PlaywrightTimeout:
            response_time = (time.time() - start_time) * 1000
            return CrawledPage(
                url=url,
                status=PageStatus.TIMEOUT,
                depth=depth,
                error_message="Page load timed out",
                response_time_ms=response_time,
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Failed to fetch page", url=url, error=str(e))
            return CrawledPage(
                url=url,
                status=PageStatus.ERROR,
                depth=depth,
                error_message=str(e),
                response_time_ms=response_time,
            )

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes URLs from the queue."""
        while True:
            try:
                url, depth = await asyncio.wait_for(self.url_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                break

            if url in self.visited_urls or len(self.crawled_pages) >= self.max_pages:
                self.url_queue.task_done()
                continue

            self.visited_urls.add(url)

            async with self._semaphore:
                logger.info("Crawling page", url=url, depth=depth, worker=worker_id)

                # Create a new page for this request
                async with self._browser_manager.new_page() as page:
                    crawled_page = await self._fetch_page(url, depth, page)
                    self.crawled_pages.append(crawled_page)

                    # Add discovered links to queue
                    if crawled_page.status == PageStatus.SUCCESS and depth < self.max_depth:
                        for link in crawled_page.links:
                            if link not in self.visited_urls:
                                await self.url_queue.put((link, depth + 1))

            self.url_queue.task_done()

    async def crawl(self) -> list[CrawledPage]:
        """Start crawling from the base URL."""
        logger.info(
            "Starting crawl",
            base_url=self.base_url,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
        )

        self._semaphore = asyncio.Semaphore(self.concurrent_requests)

        # Ensure screenshot directory exists
        if self.capture_screenshots and self.screenshot_dir:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Start with the base URL
        await self.url_queue.put((self.base_url, 0))

        # Initialize browser manager
        self._browser_manager = BrowserManager()
        await self._browser_manager.start()

        try:
            # Create worker tasks
            workers = [
                asyncio.create_task(self._worker(i))
                for i in range(self.concurrent_requests)
            ]

            # Wait for all work to complete
            await self.url_queue.join()

            # Cancel workers
            for worker in workers:
                worker.cancel()

        finally:
            # Always cleanup browser
            await self._browser_manager.stop()

        logger.info(
            "Crawl completed",
            pages_crawled=len(self.crawled_pages),
            urls_discovered=len(self.visited_urls),
        )

        return self.crawled_pages
