"""Text content extractor."""

from pathlib import Path

import aiofiles
import structlog

from ..models import CrawledPage, PageStatus
from .base import BaseExtractor

logger = structlog.get_logger()


class TextExtractor(BaseExtractor):
    """Extracts and saves plain text content from pages."""

    def __init__(self, output_dir: Path):
        super().__init__(output_dir / "text")

    async def extract(self, page: CrawledPage) -> Path | None:
        """Extract and save text content."""
        if page.status != PageStatus.SUCCESS or not page.text:
            logger.debug("Skipping text extraction", url=page.url, status=page.status)
            return None

        filename = self._url_to_filename(page.url, "txt")
        filepath = self.output_dir / filename

        try:
            # Add metadata header
            content = f"URL: {page.url}\n"
            if page.title:
                content += f"Title: {page.title}\n"
            content += f"Crawled at: {page.crawled_at.isoformat()}\n"
            content += "-" * 80 + "\n\n"
            content += page.text

            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                await f.write(content)

            logger.info("Saved text", url=page.url, path=str(filepath))
            return filepath

        except Exception as e:
            logger.error("Failed to save text", url=page.url, error=str(e))
            return None
