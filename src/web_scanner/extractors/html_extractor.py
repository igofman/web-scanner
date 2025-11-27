"""HTML content extractor."""

from pathlib import Path

import aiofiles
import structlog

from ..models import CrawledPage, PageStatus
from .base import BaseExtractor

logger = structlog.get_logger()


class HTMLExtractor(BaseExtractor):
    """Extracts and saves raw HTML content from pages."""

    def __init__(self, output_dir: Path):
        super().__init__(output_dir / "html")

    async def extract(self, page: CrawledPage) -> Path | None:
        """Extract and save HTML content."""
        if page.status != PageStatus.SUCCESS or not page.html:
            logger.debug("Skipping HTML extraction", url=page.url, status=page.status)
            return None

        filename = self._url_to_filename(page.url, "html")
        filepath = self.output_dir / filename

        try:
            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                await f.write(page.html)

            logger.info("Saved HTML", url=page.url, path=str(filepath))
            return filepath

        except Exception as e:
            logger.error("Failed to save HTML", url=page.url, error=str(e))
            return None
