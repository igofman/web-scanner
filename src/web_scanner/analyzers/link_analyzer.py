"""Link analyzer for detecting broken links and access issues."""

import asyncio
from urllib.parse import urlparse

import httpx
import structlog

from ..config import settings
from ..models import CrawledPage, LinkIssue, PageStatus
from .base import BaseAnalyzer

logger = structlog.get_logger()


class LinkAnalyzer(BaseAnalyzer):
    """Analyzes links for broken URLs and access issues."""

    def __init__(self, check_external: bool | None = None):
        self.check_external = check_external if check_external is not None else settings.check_external_links
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        self._checked_urls: dict[str, tuple[int | None, str | None]] = {}

    async def start(self) -> None:
        """Initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": settings.user_agent},
            )

    async def stop(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _check_url(self, url: str) -> tuple[int | None, str | None]:
        """
        Check if a URL is accessible.

        Returns:
            Tuple of (status_code, error_message)
        """
        # Return cached result if available
        if url in self._checked_urls:
            return self._checked_urls[url]

        async with self._semaphore:
            try:
                response = await self._client.head(url, timeout=10.0)

                # Some servers don't support HEAD, try GET
                if response.status_code == 405:
                    response = await self._client.get(url, timeout=10.0)

                result = (response.status_code, None)

            except httpx.TimeoutException:
                result = (None, "Connection timed out")
            except httpx.ConnectError as e:
                result = (None, f"Connection failed: {str(e)}")
            except httpx.TooManyRedirects:
                result = (None, "Too many redirects")
            except Exception as e:
                result = (None, f"Error: {str(e)}")

            self._checked_urls[url] = result
            return result

    async def analyze(self, pages: list[CrawledPage]) -> list[LinkIssue]:
        """
        Analyze all pages for broken links.

        Args:
            pages: List of crawled pages to analyze.

        Returns:
            List of link issues found.
        """
        await self.start()

        issues = []
        base_domains = set()

        # Collect all base domains from successful pages
        for page in pages:
            if page.status == PageStatus.SUCCESS:
                parsed = urlparse(page.url)
                base_domains.add(parsed.netloc)

        # Check links from each page
        for page in pages:
            if page.status != PageStatus.SUCCESS or not page.links:
                continue

            page_issues = await self._analyze_page_links(page, base_domains)
            issues.extend(page_issues)

        logger.info("Link analysis complete", total_issues=len(issues))
        return issues

    async def _analyze_page_links(
        self, page: CrawledPage, base_domains: set[str]
    ) -> list[LinkIssue]:
        """Analyze links from a single page."""
        issues = []
        tasks = []

        for link in page.links:
            parsed = urlparse(link)
            is_internal = parsed.netloc in base_domains

            # Skip external links if not configured to check them
            if not is_internal and not self.check_external:
                continue

            tasks.append(self._check_link(page.url, link))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, LinkIssue):
                    issues.append(result)

        return issues

    async def _check_link(self, source_url: str, target_url: str) -> LinkIssue | None:
        """Check a single link and return issue if broken."""
        status_code, error_message = await self._check_url(target_url)

        # Determine if this is an issue
        is_issue = False
        error_type = ""

        if error_message:
            is_issue = True
            error_type = "connection_error"
        elif status_code:
            if status_code == 404:
                is_issue = True
                error_type = "not_found"
                error_message = "Page not found (404)"
            elif status_code == 403:
                is_issue = True
                error_type = "forbidden"
                error_message = "Access forbidden (403)"
            elif status_code == 401:
                is_issue = True
                error_type = "unauthorized"
                error_message = "Authentication required (401)"
            elif status_code >= 500:
                is_issue = True
                error_type = "server_error"
                error_message = f"Server error ({status_code})"

        if is_issue:
            return LinkIssue(
                source_url=source_url,
                target_url=target_url,
                status_code=status_code,
                error_type=error_type,
                error_message=error_message or "Unknown error",
            )

        return None

    async def analyze_single_page(self, page: CrawledPage) -> list[LinkIssue]:
        """Analyze links from a single page."""
        await self.start()

        if page.status != PageStatus.SUCCESS or not page.links:
            return []

        base_domain = urlparse(page.url).netloc
        return await self._analyze_page_links(page, {base_domain})
