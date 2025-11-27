"""Tests for data models."""

import pytest
from datetime import datetime

from web_scanner.models import (
    CrawledPage,
    PageStatus,
    ExtractedData,
    GrammarIssue,
    LinkIssue,
    AnalysisReport,
)


class TestCrawledPage:
    """Test cases for CrawledPage model."""

    def test_create_success_page(self):
        """Test creating a successful page."""
        page = CrawledPage(
            url="https://example.com",
            status=PageStatus.SUCCESS,
            status_code=200,
            html="<html></html>",
            text="Test content",
            title="Test Page",
            links=["https://example.com/about"],
        )

        assert page.url == "https://example.com"
        assert page.status == PageStatus.SUCCESS
        assert page.status_code == 200
        assert len(page.links) == 1

    def test_create_error_page(self):
        """Test creating an error page."""
        page = CrawledPage(
            url="https://example.com/broken",
            status=PageStatus.ERROR,
            error_message="Connection refused",
        )

        assert page.status == PageStatus.ERROR
        assert page.error_message == "Connection refused"
        assert page.html is None

    def test_default_values(self):
        """Test default values are set correctly."""
        page = CrawledPage(
            url="https://example.com",
            status=PageStatus.SUCCESS,
        )

        assert page.links == []
        assert page.depth == 0
        assert isinstance(page.crawled_at, datetime)


class TestAnalysisReport:
    """Test cases for AnalysisReport model."""

    def test_create_empty_report(self):
        """Test creating an empty report."""
        report = AnalysisReport(
            base_url="https://example.com",
            scan_started=datetime.now(),
        )

        assert report.pages_crawled == 0
        assert report.grammar_issues == []
        assert report.link_issues == []
        assert report.ocr_issues == []

    def test_add_issues(self):
        """Test adding issues to report."""
        report = AnalysisReport(
            base_url="https://example.com",
            scan_started=datetime.now(),
        )

        report.grammar_issues.append(
            GrammarIssue(
                message="Possible spelling mistake",
                context="teh quick brown fox",
                suggestions=["the"],
                offset=0,
                length=3,
                rule_id="MORFOLOGIK_RULE_EN_US",
                category="TYPOS",
            )
        )

        report.link_issues.append(
            LinkIssue(
                source_url="https://example.com",
                target_url="https://example.com/broken",
                status_code=404,
                error_type="not_found",
                error_message="Page not found (404)",
            )
        )

        assert len(report.grammar_issues) == 1
        assert len(report.link_issues) == 1
