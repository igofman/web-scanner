"""Data models for the web scanner."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class PageStatus(Enum):
    """Status of a crawled page."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"


@dataclass
class CrawledPage:
    """Represents a crawled page with its metadata."""

    url: str
    status: PageStatus
    status_code: int | None = None
    content_type: str | None = None
    html: str | None = None
    text: str | None = None
    title: str | None = None
    links: list[str] = field(default_factory=list)
    depth: int = 0
    crawled_at: datetime = field(default_factory=datetime.now)
    error_message: str | None = None
    response_time_ms: float | None = None
    screenshot_path: str | None = None  # Path to captured screenshot


@dataclass
class ExtractedData:
    """Container for all extracted data from a page."""

    url: str
    html_path: Path | None = None
    text_path: Path | None = None
    screenshot_path: Path | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GrammarIssue:
    """Represents a grammar or spelling issue."""

    message: str
    context: str
    suggestions: list[str]
    offset: int
    length: int
    rule_id: str
    category: str


@dataclass
class LinkIssue:
    """Represents a broken or problematic link."""

    source_url: str
    target_url: str
    status_code: int | None
    error_type: str
    error_message: str


@dataclass
class OCRIssue:
    """Represents an issue found via OCR analysis."""

    screenshot_path: str
    extracted_text: str
    issue_type: str
    description: str
    confidence: float


@dataclass
class AnalysisReport:
    """Complete analysis report for a scanned website."""

    base_url: str
    scan_started: datetime
    scan_completed: datetime | None = None
    pages_crawled: int = 0
    pages_analyzed: int = 0
    grammar_issues: list[GrammarIssue] = field(default_factory=list)
    link_issues: list[LinkIssue] = field(default_factory=list)
    ocr_issues: list[OCRIssue] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
