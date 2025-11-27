"""Tests for extractor modules."""

import pytest
from pathlib import Path

from web_scanner.extractors.base import BaseExtractor


class ConcreteExtractor(BaseExtractor):
    """Concrete implementation for testing."""

    async def extract(self, page):
        return None


class TestBaseExtractor:
    """Test cases for BaseExtractor."""

    def test_url_to_filename_simple(self, tmp_path):
        """Test simple URL to filename conversion."""
        extractor = ConcreteExtractor(tmp_path)

        filename = extractor._url_to_filename("https://example.com/about", "html")
        assert filename == "about.html"

    def test_url_to_filename_index(self, tmp_path):
        """Test root URL to filename conversion."""
        extractor = ConcreteExtractor(tmp_path)

        filename = extractor._url_to_filename("https://example.com/", "html")
        assert filename == "index.html"

        filename = extractor._url_to_filename("https://example.com", "html")
        assert filename == "index.html"

    def test_url_to_filename_nested(self, tmp_path):
        """Test nested path URL to filename conversion."""
        extractor = ConcreteExtractor(tmp_path)

        filename = extractor._url_to_filename("https://example.com/blog/post/123", "txt")
        assert filename == "blog_post_123.txt"

    def test_url_to_filename_with_query(self, tmp_path):
        """Test URL with query string to filename conversion."""
        extractor = ConcreteExtractor(tmp_path)

        filename = extractor._url_to_filename("https://example.com/search?q=test&page=1", "html")
        assert "search" in filename
        assert "q-test" in filename
        assert ".html" in filename

    def test_url_to_filename_sanitizes(self, tmp_path):
        """Test that special characters are sanitized."""
        extractor = ConcreteExtractor(tmp_path)

        filename = extractor._url_to_filename("https://example.com/path/with spaces/file", "txt")
        assert " " not in filename
        assert ".txt" in filename

    def test_creates_output_directory(self, tmp_path):
        """Test that output directory is created."""
        output_dir = tmp_path / "nested" / "output"
        extractor = ConcreteExtractor(output_dir)

        assert output_dir.exists()
