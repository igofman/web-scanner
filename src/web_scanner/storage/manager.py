"""Storage manager for organizing extracted data."""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import aiofiles
import structlog

from ..config import settings
from ..models import CrawledPage, ExtractedData, AnalysisReport

logger = structlog.get_logger()


class StorageManager:
    """Manages storage of extracted data and reports."""

    def __init__(self, base_url: str, output_dir: Path | None = None):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc

        # Create a unique folder for each scan
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{self._sanitize_domain(self.domain)}_{timestamp}"

        self.output_dir = (output_dir or settings.output_dir) / folder_name
        self.reports_dir = settings.reports_dir / folder_name

        self._setup_directories()

    def _sanitize_domain(self, domain: str) -> str:
        """Convert domain to safe folder name."""
        return domain.replace(":", "_").replace("/", "_").replace(".", "_")

    def _setup_directories(self) -> None:
        """Create necessary directory structure."""
        directories = [
            self.output_dir,
            self.output_dir / "html",
            self.output_dir / "text",
            self.output_dir / "screenshots",
            self.output_dir / "metadata",
            self.reports_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        logger.info("Storage directories created", output_dir=str(self.output_dir))

    def get_output_dir(self) -> Path:
        """Get the output directory path."""
        return self.output_dir

    def get_reports_dir(self) -> Path:
        """Get the reports directory path."""
        return self.reports_dir

    async def save_crawl_metadata(self, pages: list[CrawledPage]) -> Path:
        """Save crawl metadata as JSON."""
        metadata = {
            "base_url": self.base_url,
            "domain": self.domain,
            "crawled_at": datetime.now().isoformat(),
            "total_pages": len(pages),
            "pages": [
                {
                    "url": page.url,
                    "status": page.status.value,
                    "status_code": page.status_code,
                    "title": page.title,
                    "depth": page.depth,
                    "links_count": len(page.links),
                    "response_time_ms": page.response_time_ms,
                    "crawled_at": page.crawled_at.isoformat(),
                    "error_message": page.error_message,
                }
                for page in pages
            ],
        }

        filepath = self.output_dir / "metadata" / "crawl_metadata.json"

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(metadata, indent=2))

        logger.info("Saved crawl metadata", path=str(filepath))
        return filepath

    async def save_extracted_data_index(self, data: list[ExtractedData]) -> Path:
        """Save index of extracted data."""
        index = {
            "base_url": self.base_url,
            "extracted_at": datetime.now().isoformat(),
            "total_pages": len(data),
            "pages": [
                {
                    "url": item.url,
                    "html_path": str(item.html_path) if item.html_path else None,
                    "text_path": str(item.text_path) if item.text_path else None,
                    "screenshot_path": str(item.screenshot_path) if item.screenshot_path else None,
                    "metadata": item.metadata,
                }
                for item in data
            ],
        }

        filepath = self.output_dir / "metadata" / "extraction_index.json"

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(index, indent=2))

        logger.info("Saved extraction index", path=str(filepath))
        return filepath

    async def save_analysis_report(self, report: AnalysisReport) -> Path:
        """Save the complete analysis report."""
        report_data = {
            "base_url": report.base_url,
            "scan_started": report.scan_started.isoformat(),
            "scan_completed": report.scan_completed.isoformat() if report.scan_completed else None,
            "summary": {
                "pages_crawled": report.pages_crawled,
                "pages_analyzed": report.pages_analyzed,
                "total_grammar_issues": len(report.grammar_issues),
                "total_link_issues": len(report.link_issues),
                "total_ocr_issues": len(report.ocr_issues),
                "total_errors": len(report.errors),
            },
            "grammar_issues": [
                {
                    "message": issue.message,
                    "context": issue.context,
                    "suggestions": issue.suggestions,
                    "offset": issue.offset,
                    "length": issue.length,
                    "rule_id": issue.rule_id,
                    "category": issue.category,
                }
                for issue in report.grammar_issues
            ],
            "link_issues": [
                {
                    "source_url": issue.source_url,
                    "target_url": issue.target_url,
                    "status_code": issue.status_code,
                    "error_type": issue.error_type,
                    "error_message": issue.error_message,
                }
                for issue in report.link_issues
            ],
            "ocr_issues": [
                {
                    "screenshot_path": issue.screenshot_path,
                    "extracted_text": issue.extracted_text,
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                    "confidence": issue.confidence,
                }
                for issue in report.ocr_issues
            ],
            "errors": report.errors,
        }

        filepath = self.reports_dir / "analysis_report.json"

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(report_data, indent=2))

        # Also save a human-readable summary
        summary_path = self.reports_dir / "summary.txt"
        await self._save_human_readable_summary(report, summary_path)

        logger.info("Saved analysis report", path=str(filepath))
        return filepath

    async def _save_human_readable_summary(self, report: AnalysisReport, filepath: Path) -> None:
        """Save a human-readable summary of the analysis."""
        lines = [
            "=" * 80,
            "WEB SCANNER ANALYSIS REPORT",
            "=" * 80,
            "",
            f"Website: {report.base_url}",
            f"Scan Started: {report.scan_started}",
            f"Scan Completed: {report.scan_completed}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Pages Crawled: {report.pages_crawled}",
            f"Pages Analyzed: {report.pages_analyzed}",
            f"Grammar Issues: {len(report.grammar_issues)}",
            f"Broken Links: {len(report.link_issues)}",
            f"OCR Issues: {len(report.ocr_issues)}",
            f"Errors: {len(report.errors)}",
            "",
        ]

        if report.grammar_issues:
            lines.extend([
                "GRAMMAR ISSUES",
                "-" * 40,
            ])
            for i, issue in enumerate(report.grammar_issues[:20], 1):  # Limit to first 20
                lines.extend([
                    f"{i}. {issue.message}",
                    f"   Context: ...{issue.context}...",
                    f"   Suggestions: {', '.join(issue.suggestions[:3])}",
                    "",
                ])
            if len(report.grammar_issues) > 20:
                lines.append(f"   ... and {len(report.grammar_issues) - 20} more issues")
            lines.append("")

        if report.link_issues:
            lines.extend([
                "BROKEN LINKS",
                "-" * 40,
            ])
            for i, issue in enumerate(report.link_issues[:20], 1):
                lines.extend([
                    f"{i}. {issue.target_url}",
                    f"   Source: {issue.source_url}",
                    f"   Error: {issue.error_type} - {issue.error_message}",
                    "",
                ])
            if len(report.link_issues) > 20:
                lines.append(f"   ... and {len(report.link_issues) - 20} more issues")
            lines.append("")

        if report.ocr_issues:
            lines.extend([
                "OCR ISSUES (from screenshots)",
                "-" * 40,
            ])
            for i, issue in enumerate(report.ocr_issues[:20], 1):
                lines.extend([
                    f"{i}. {issue.issue_type}",
                    f"   Description: {issue.description}",
                    f"   Confidence: {issue.confidence:.2f}",
                    "",
                ])
            if len(report.ocr_issues) > 20:
                lines.append(f"   ... and {len(report.ocr_issues) - 20} more issues")

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write("\n".join(lines))
