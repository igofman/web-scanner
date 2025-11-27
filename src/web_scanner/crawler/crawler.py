"""Core web crawler implementation."""

import asyncio
import time
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from ..config import settings
from ..models import CrawledPage, PageStatus

logger = structlog.get_logger()


class WebCrawler:
    """Recursive web crawler that discovers and fetches pages."""

    def __init__(
        self,
        base_url: str,
        max_depth: int | None = None,
        max_pages: int | None = None,
        concurrent_requests: int | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.base_domain = urlparse(base_url).netloc
        self.max_depth = max_depth or settings.max_depth
        self.max_pages = max_pages or settings.max_pages
        self.concurrent_requests = concurrent_requests or settings.concurrent_requests

        self.visited_urls: set[str] = set()
        self.crawled_pages: list[CrawledPage] = []
        self.url_queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self._semaphore: asyncio.Semaphore | None = None

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
                ".ttf", ".eot",
            )
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in skip_extensions):
                return False

            return True
        except Exception:
            return False

    def _extract_links(self, html: str, current_url: str) -> list[str]:
        """Extract all valid links from HTML content."""
        links = []
        try:
            soup = BeautifulSoup(html, "lxml")
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"]

                # Skip javascript, mailto, tel links
                if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue

                # Convert relative URLs to absolute
                absolute_url = urljoin(current_url, href)
                normalized = self._normalize_url(absolute_url)

                if self._is_valid_url(normalized):
                    links.append(normalized)
        except Exception as e:
            logger.warning("Error extracting links", url=current_url, error=str(e))

        return list(set(links))

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML content."""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Remove script and style elements
            for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Clean up multiple newlines
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
        except Exception:
            return ""

    def _extract_title(self, html: str) -> str | None:
        """Extract page title from HTML."""
        try:
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            return title_tag.get_text(strip=True) if title_tag else None
        except Exception:
            return None

    async def _fetch_page(self, url: str, depth: int, client: httpx.AsyncClient) -> CrawledPage:
        """Fetch a single page and extract its content."""
        start_time = time.time()

        try:
            response = await client.get(
                url,
                timeout=settings.request_timeout,
                follow_redirects=True,
            )
            response_time = (time.time() - start_time) * 1000

            content_type = response.headers.get("content-type", "")

            # Only process HTML pages
            if "text/html" not in content_type:
                return CrawledPage(
                    url=url,
                    status=PageStatus.SUCCESS,
                    status_code=response.status_code,
                    content_type=content_type,
                    depth=depth,
                    response_time_ms=response_time,
                )

            html = response.text
            text = self._extract_text(html)
            title = self._extract_title(html)
            links = self._extract_links(html, url)

            return CrawledPage(
                url=url,
                status=PageStatus.SUCCESS,
                status_code=response.status_code,
                content_type=content_type,
                html=html,
                text=text,
                title=title,
                links=links,
                depth=depth,
                response_time_ms=response_time,
            )

        except httpx.TimeoutException:
            return CrawledPage(
                url=url,
                status=PageStatus.TIMEOUT,
                depth=depth,
                error_message="Request timed out",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except httpx.HTTPStatusError as e:
            status = PageStatus.NOT_FOUND if e.response.status_code == 404 else PageStatus.ERROR
            return CrawledPage(
                url=url,
                status=status,
                status_code=e.response.status_code,
                depth=depth,
                error_message=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return CrawledPage(
                url=url,
                status=PageStatus.ERROR,
                depth=depth,
                error_message=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _worker(self, client: httpx.AsyncClient) -> None:
        """Worker coroutine that processes URLs from the queue."""
        while True:
            try:
                url, depth = await asyncio.wait_for(self.url_queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                break

            if url in self.visited_urls or len(self.crawled_pages) >= self.max_pages:
                self.url_queue.task_done()
                continue

            self.visited_urls.add(url)

            async with self._semaphore:
                logger.info("Crawling page", url=url, depth=depth)
                page = await self._fetch_page(url, depth, client)
                self.crawled_pages.append(page)

                # Add discovered links to queue
                if page.status == PageStatus.SUCCESS and depth < self.max_depth:
                    for link in page.links:
                        if link not in self.visited_urls:
                            await self.url_queue.put((link, depth + 1))

            self.url_queue.task_done()

    async def crawl(self) -> list[CrawledPage]:
        """Start crawling from the base URL."""
        logger.info("Starting crawl", base_url=self.base_url, max_depth=self.max_depth)

        self._semaphore = asyncio.Semaphore(self.concurrent_requests)

        # Start with the base URL
        await self.url_queue.put((self.base_url, 0))

        headers = {"User-Agent": settings.user_agent}

        async with httpx.AsyncClient(headers=headers) as client:
            # Create worker tasks
            workers = [
                asyncio.create_task(self._worker(client))
                for _ in range(self.concurrent_requests)
            ]

            # Wait for all work to complete
            await self.url_queue.join()

            # Cancel workers
            for worker in workers:
                worker.cancel()

        logger.info(
            "Crawl completed",
            pages_crawled=len(self.crawled_pages),
            urls_discovered=len(self.visited_urls),
        )

        return self.crawled_pages
