"""Main orchestrator that coordinates crawling, extraction, and analysis."""

import asyncio
from datetime import datetime
from pathlib import Path

import structlog

from .config import settings
from .crawler import WebCrawler
from .extractors import HTMLExtractor, TextExtractor
from .analyzers import GrammarAnalyzer, LinkAnalyzer, OCRAnalyzer
from .storage import StorageManager
from .models import AnalysisReport, CrawledPage, ExtractedData, PageStatus

logger = structlog.get_logger()


class ScanOrchestrator:
    """Orchestrates the complete website scanning and analysis workflow.

    The new architecture uses Playwright for both crawling and screenshots,
    capturing screenshots during the crawl phase for better accuracy with
    JavaScript-rendered content.
    """

    def __init__(
        self,
        url: str,
        max_depth: int | None = None,
        max_pages: int | None = None,
        skip_screenshots: bool = False,
        skip_grammar: bool = False,
        skip_links: bool = False,
        skip_ocr: bool = False,
        output_dir: Path | None = None,
    ):
        self.url = url
        self.max_depth = max_depth or settings.max_depth
        self.max_pages = max_pages or settings.max_pages
        self.skip_screenshots = skip_screenshots
        self.skip_grammar = skip_grammar
        self.skip_links = skip_links
        self.skip_ocr = skip_ocr or skip_screenshots  # Can't do OCR without screenshots

        # Initialize storage
        self.storage = StorageManager(url, output_dir)

        # Screenshot directory (used during crawl)
        self.screenshot_dir = self.storage.get_output_dir() / "screenshots" if not skip_screenshots else None

        # Initialize crawler with integrated screenshot support
        self.crawler = WebCrawler(
            url,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
            screenshot_dir=self.screenshot_dir,
            capture_screenshots=not skip_screenshots,
        )

        # Initialize extractors (for saving HTML/text to files)
        self.html_extractor = HTMLExtractor(self.storage.get_output_dir())
        self.text_extractor = TextExtractor(self.storage.get_output_dir())

        # Initialize analyzers
        self.grammar_analyzer = GrammarAnalyzer() if not skip_grammar else None
        self.link_analyzer = LinkAnalyzer() if not skip_links else None
        self.ocr_analyzer = OCRAnalyzer() if not self.skip_ocr else None

        # Results
        self.crawled_pages: list[CrawledPage] = []
        self.extracted_data: list[ExtractedData] = []
        self.report: AnalysisReport | None = None

    async def run(self) -> AnalysisReport:
        """Run the complete scan workflow."""
        logger.info("Starting scan", url=self.url)
        start_time = datetime.now()

        self.report = AnalysisReport(
            base_url=self.url,
            scan_started=start_time,
        )

        try:
            # Phase 1: Crawl (includes screenshots with Playwright)
            logger.info("Phase 1: Crawling website with Playwright (JavaScript enabled)")
            self.crawled_pages = await self.crawler.crawl()
            self.report.pages_crawled = len(self.crawled_pages)

            # Save crawl metadata
            await self.storage.save_crawl_metadata(self.crawled_pages)

            # Phase 2: Extract and save content to files
            logger.info("Phase 2: Saving extracted content")
            await self._save_extracted_content()

            # Save extraction index
            await self.storage.save_extracted_data_index(self.extracted_data)

            # Phase 3: Analyze
            logger.info("Phase 3: Analyzing content")
            await self._analyze_content()

            self.report.scan_completed = datetime.now()
            self.report.pages_analyzed = len([
                p for p in self.crawled_pages if p.status == PageStatus.SUCCESS
            ])

            # Save final report
            report_path = await self.storage.save_analysis_report(self.report)
            logger.info(
                "Scan completed",
                duration=str(self.report.scan_completed - start_time),
                report_path=str(report_path),
            )

            return self.report

        except Exception as e:
            logger.error("Scan failed", error=str(e))
            self.report.errors.append(f"Scan failed: {str(e)}")
            self.report.scan_completed = datetime.now()
            await self.storage.save_analysis_report(self.report)
            raise

        finally:
            await self._cleanup()

    async def _save_extracted_content(self) -> None:
        """Save extracted content (HTML, text) to files.

        Screenshots are already captured during crawl phase.
        """
        successful_pages = [p for p in self.crawled_pages if p.status == PageStatus.SUCCESS]

        for page in successful_pages:
            extracted = ExtractedData(url=page.url)

            # Save HTML and text in parallel
            html_task = self.html_extractor.extract(page)
            text_task = self.text_extractor.extract(page)

            results = await asyncio.gather(html_task, text_task, return_exceptions=True)

            if not isinstance(results[0], Exception):
                extracted.html_path = results[0]
            if not isinstance(results[1], Exception):
                extracted.text_path = results[1]

            # Screenshot was captured during crawl
            if page.screenshot_path:
                extracted.screenshot_path = Path(page.screenshot_path)

            self.extracted_data.append(extracted)

    async def _analyze_content(self) -> None:
        """Run all analyzers on extracted content."""
        tasks = []

        # Grammar analysis
        if self.grammar_analyzer:
            tasks.append(self._run_grammar_analysis())

        # Link analysis
        if self.link_analyzer:
            tasks.append(self._run_link_analysis())

        # OCR analysis
        if self.ocr_analyzer:
            tasks.append(self._run_ocr_analysis())

        # Run analyses in parallel
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_grammar_analysis(self) -> None:
        """Run grammar analysis on extracted text."""
        logger.info("Running grammar analysis")

        try:
            for extracted in self.extracted_data:
                if extracted.text_path:
                    issues = await self.grammar_analyzer.analyze(extracted.text_path)
                    self.report.grammar_issues.extend(issues)

            logger.info("Grammar analysis complete", issues=len(self.report.grammar_issues))

        except Exception as e:
            logger.error("Grammar analysis failed", error=str(e))
            self.report.errors.append(f"Grammar analysis error: {str(e)}")

        finally:
            await self.grammar_analyzer.stop()

    async def _run_link_analysis(self) -> None:
        """Run link analysis on crawled pages."""
        logger.info("Running link analysis")

        try:
            issues = await self.link_analyzer.analyze(self.crawled_pages)
            self.report.link_issues.extend(issues)
            logger.info("Link analysis complete", issues=len(self.report.link_issues))

        except Exception as e:
            logger.error("Link analysis failed", error=str(e))
            self.report.errors.append(f"Link analysis error: {str(e)}")

        finally:
            await self.link_analyzer.stop()

    async def _run_ocr_analysis(self) -> None:
        """Run OCR analysis on screenshots."""
        logger.info("Running OCR analysis")

        try:
            screenshot_paths = [
                extracted.screenshot_path
                for extracted in self.extracted_data
                if extracted.screenshot_path
            ]

            if screenshot_paths:
                issues = await self.ocr_analyzer.analyze_batch(screenshot_paths)
                self.report.ocr_issues.extend(issues)

            logger.info("OCR analysis complete", issues=len(self.report.ocr_issues))

        except Exception as e:
            logger.error("OCR analysis failed", error=str(e))
            self.report.errors.append(f"OCR analysis error: {str(e)}")

        finally:
            await self.ocr_analyzer.stop()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self.grammar_analyzer:
            await self.grammar_analyzer.stop()

        if self.link_analyzer:
            await self.link_analyzer.stop()

        if self.ocr_analyzer:
            await self.ocr_analyzer.stop()
