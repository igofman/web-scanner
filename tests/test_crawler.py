"""Tests for the web crawler module."""

import pytest
from web_scanner.crawler import WebCrawler


class TestWebCrawler:
    """Test cases for WebCrawler."""

    def test_normalize_url(self):
        """Test URL normalization."""
        crawler = WebCrawler("https://example.com")

        assert crawler._normalize_url("https://example.com/") == "https://example.com"
        assert crawler._normalize_url("https://example.com/page#section") == "https://example.com/page"
        assert crawler._normalize_url("https://example.com/page?q=1") == "https://example.com/page?q=1"

    def test_is_valid_url_same_domain(self):
        """Test that same domain URLs are valid."""
        crawler = WebCrawler("https://example.com")

        assert crawler._is_valid_url("https://example.com/page") is True
        assert crawler._is_valid_url("https://example.com/about") is True
        assert crawler._is_valid_url("https://other.com/page") is False

    def test_is_valid_url_skips_resources(self):
        """Test that non-HTML resources are skipped."""
        crawler = WebCrawler("https://example.com")

        assert crawler._is_valid_url("https://example.com/image.png") is False
        assert crawler._is_valid_url("https://example.com/style.css") is False
        assert crawler._is_valid_url("https://example.com/script.js") is False
        assert crawler._is_valid_url("https://example.com/doc.pdf") is False

    def test_extract_links(self):
        """Test link extraction from HTML."""
        crawler = WebCrawler("https://example.com")

        html = """
        <html>
            <body>
                <a href="/about">About</a>
                <a href="https://example.com/contact">Contact</a>
                <a href="https://external.com">External</a>
                <a href="mailto:test@test.com">Email</a>
            </body>
        </html>
        """

        links = crawler._extract_links(html, "https://example.com")

        assert "https://example.com/about" in links
        assert "https://example.com/contact" in links
        # External links should be filtered out
        assert "https://external.com" not in links
        # Mailto links should be filtered out
        assert "mailto:test@test.com" not in links

    def test_extract_text(self):
        """Test text extraction from HTML."""
        crawler = WebCrawler("https://example.com")

        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <script>console.log('test');</script>
                <style>.test { color: red; }</style>
                <h1>Hello World</h1>
                <p>This is a test paragraph.</p>
            </body>
        </html>
        """

        text = crawler._extract_text(html)

        assert "Hello World" in text
        assert "This is a test paragraph" in text
        assert "console.log" not in text
        assert "color: red" not in text

    def test_extract_title(self):
        """Test title extraction from HTML."""
        crawler = WebCrawler("https://example.com")

        html = "<html><head><title>Test Page Title</title></head><body></body></html>"
        assert crawler._extract_title(html) == "Test Page Title"

        html_no_title = "<html><head></head><body></body></html>"
        assert crawler._extract_title(html_no_title) is None
