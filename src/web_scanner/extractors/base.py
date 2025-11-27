"""Base extractor interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import CrawledPage


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def extract(self, page: CrawledPage) -> Path | None:
        """
        Extract content from a crawled page and save to disk.

        Args:
            page: The crawled page to extract content from.

        Returns:
            Path to the saved file, or None if extraction failed.
        """
        pass

    def _url_to_filename(self, url: str, extension: str) -> str:
        """Convert a URL to a safe filename."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.strip("/").replace("/", "_") or "index"

        if parsed.query:
            query_safe = parsed.query.replace("&", "_").replace("=", "-")
            path = f"{path}_{query_safe}"

        # Truncate if too long
        if len(path) > 200:
            path = path[:200]

        # Remove any unsafe characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        path = "".join(c if c in safe_chars else "_" for c in path)

        return f"{path}.{extension}"
