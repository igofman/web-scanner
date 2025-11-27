"""AI-powered content analyzer using OpenRouter."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from ..analyzers.base import BaseAnalyzer
from ..models import CrawledPage, ExtractedData
from .client import OpenRouterClient

logger = structlog.get_logger()


@dataclass
class AIIssue:
    """Represents an issue found by AI analysis."""

    severity: str  # critical, warning, info
    category: str  # Grammar, HTML, Visual, etc.
    description: str
    location: str | None = None
    suggestion: str | None = None
    original: str | None = None
    source_url: str | None = None
    source_type: str | None = None  # text, html, screenshot
    bbox: list[float] | None = None  # Normalized bounding box [x, y, w, h]
    evidence: str | None = None  # OCR text or visual cue observed
    confidence: int | None = None  # 1-5 confidence score


@dataclass
class TextCorrection:
    """Represents a text correction found in screenshot analysis."""

    original: str
    correction: str
    explanation: str
    bbox: list[float] | None = None
    confidence: int | None = None


@dataclass
class AIAnalysisResult:
    """Complete AI analysis result for a page."""

    url: str
    text_issues: list[AIIssue] = field(default_factory=list)
    html_issues: list[AIIssue] = field(default_factory=list)
    visual_issues: list[AIIssue] = field(default_factory=list)
    text_corrections: list[TextCorrection] = field(default_factory=list)
    text_summary: str | None = None
    html_summary: str | None = None
    visual_summary: str | None = None
    visual_score: float | None = None
    errors: list[str] = field(default_factory=list)


class AIAnalyzer(BaseAnalyzer):
    """AI-powered analyzer for comprehensive content analysis."""

    def __init__(
        self,
        api_key: str | None = None,
        analyze_text: bool = True,
        analyze_html: bool = True,
        analyze_screenshots: bool = True,
        model: str | None = None,
        vision_model: str | None = None,
    ):
        self.analyze_text_enabled = analyze_text
        self.analyze_html_enabled = analyze_html
        self.analyze_screenshots_enabled = analyze_screenshots
        self._client: OpenRouterClient | None = None
        self._api_key = api_key
        self._model = model
        self._vision_model = vision_model

    async def start(self) -> None:
        """Initialize the OpenRouter client."""
        if self._client is None:
            self._client = OpenRouterClient(
                api_key=self._api_key,
                model=self._model,
                vision_model=self._vision_model,
            )
            await self._client.start()
            logger.info("AI Analyzer initialized")

    async def stop(self) -> None:
        """Close the OpenRouter client."""
        if self._client:
            await self._client.stop()
            self._client = None
            logger.info("AI Analyzer stopped")

    async def analyze(self, data: Any) -> list[AIIssue]:
        """Analyze data and return issues (required by BaseAnalyzer)."""
        # This method is for compatibility with BaseAnalyzer
        # Use analyze_page or analyze_batch for full functionality
        return []

    async def analyze_page(
        self,
        page: CrawledPage,
        extracted: ExtractedData | None = None,
    ) -> AIAnalysisResult:
        """
        Analyze a single page with AI.

        Args:
            page: The crawled page data
            extracted: Optional extracted data with file paths

        Returns:
            AIAnalysisResult with all issues found
        """
        await self.start()
        result = AIAnalysisResult(url=page.url)

        tasks = []

        # Analyze text content
        if self.analyze_text_enabled and page.text:
            tasks.append(self._analyze_text(page.text, page.url, result))

        # Analyze HTML content
        if self.analyze_html_enabled and page.html:
            tasks.append(self._analyze_html(page.html, page.url, result))

        # Analyze screenshot
        screenshot_path = None
        if extracted and extracted.screenshot_path:
            screenshot_path = extracted.screenshot_path
        elif page.screenshot_path:
            screenshot_path = Path(page.screenshot_path)

        if self.analyze_screenshots_enabled and screenshot_path:
            tasks.append(self._analyze_screenshot(screenshot_path, page.url, result))

        # Run analyses concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return result

    async def analyze_batch(
        self,
        pages: list[CrawledPage],
        extracted_data: list[ExtractedData] | None = None,
        concurrency: int = 2,
    ) -> list[AIAnalysisResult]:
        """
        Analyze multiple pages with AI.

        Args:
            pages: List of crawled pages
            extracted_data: Optional list of extracted data
            concurrency: Number of concurrent analyses

        Returns:
            List of AIAnalysisResult for each page
        """
        await self.start()

        # Create a mapping of URL to extracted data
        extracted_map = {}
        if extracted_data:
            for ed in extracted_data:
                extracted_map[ed.url] = ed

        semaphore = asyncio.Semaphore(concurrency)

        async def analyze_with_semaphore(page: CrawledPage) -> AIAnalysisResult:
            async with semaphore:
                extracted = extracted_map.get(page.url)
                logger.info("AI analyzing page", url=page.url)
                return await self.analyze_page(page, extracted)

        tasks = [analyze_with_semaphore(page) for page in pages]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and convert to results
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "AI analysis failed for page",
                    url=pages[i].url,
                    error=str(result),
                )
                valid_results.append(AIAnalysisResult(
                    url=pages[i].url,
                    errors=[str(result)],
                ))
            else:
                valid_results.append(result)

        return valid_results

    async def _analyze_text(
        self,
        text: str,
        url: str,
        result: AIAnalysisResult,
    ) -> None:
        """Analyze text content."""
        try:
            logger.debug("Analyzing text content", url=url)
            analysis = await self._client.analyze_text(text, analysis_type="general")

            if "issues" in analysis:
                for issue_data in analysis["issues"]:
                    issue = AIIssue(
                        severity=issue_data.get("severity", "info"),
                        category=issue_data.get("category", "Text"),
                        description=issue_data.get("description", ""),
                        location=issue_data.get("location"),
                        suggestion=issue_data.get("suggestion"),
                        original=issue_data.get("original"),
                        source_url=url,
                        source_type="text",
                    )
                    result.text_issues.append(issue)

            result.text_summary = analysis.get("summary")
            logger.info(
                "Text analysis complete",
                url=url,
                issues=len(result.text_issues),
            )

        except Exception as e:
            error_msg = f"Text analysis failed: {str(e)}"
            logger.error(error_msg, url=url)
            result.errors.append(error_msg)

    async def _analyze_html(
        self,
        html: str,
        url: str,
        result: AIAnalysisResult,
    ) -> None:
        """Analyze HTML content."""
        try:
            logger.debug("Analyzing HTML content", url=url)
            analysis = await self._client.analyze_html(html, url=url)

            if "issues" in analysis:
                for issue_data in analysis["issues"]:
                    issue = AIIssue(
                        severity=issue_data.get("severity", "info"),
                        category=issue_data.get("category", "HTML"),
                        description=issue_data.get("description", ""),
                        location=issue_data.get("location"),
                        suggestion=issue_data.get("suggestion"),
                        source_url=url,
                        source_type="html",
                    )
                    result.html_issues.append(issue)

            result.html_summary = analysis.get("summary")
            logger.info(
                "HTML analysis complete",
                url=url,
                issues=len(result.html_issues),
            )

        except Exception as e:
            error_msg = f"HTML analysis failed: {str(e)}"
            logger.error(error_msg, url=url)
            result.errors.append(error_msg)

    async def _analyze_screenshot(
        self,
        screenshot_path: Path | str,
        url: str,
        result: AIAnalysisResult,
    ) -> None:
        """Analyze screenshot for visual issues."""
        try:
            logger.debug("Analyzing screenshot", url=url, path=str(screenshot_path))
            analysis = await self._client.analyze_image(screenshot_path, page_url=url)

            if "issues" in analysis:
                for issue_data in analysis["issues"]:
                    issue = AIIssue(
                        severity=issue_data.get("severity", "info"),
                        category=issue_data.get("category", "Visual"),
                        description=issue_data.get("description", ""),
                        location=issue_data.get("location"),
                        suggestion=issue_data.get("suggestion"),
                        source_url=url,
                        source_type="screenshot",
                        bbox=issue_data.get("bbox"),
                        evidence=issue_data.get("evidence"),
                        confidence=issue_data.get("confidence"),
                    )
                    result.visual_issues.append(issue)

            # Parse text corrections from enhanced analysis
            if "text_corrections" in analysis:
                for correction_data in analysis["text_corrections"]:
                    correction = TextCorrection(
                        original=correction_data.get("original", ""),
                        correction=correction_data.get("correction", ""),
                        explanation=correction_data.get("explanation", ""),
                        bbox=correction_data.get("bbox"),
                        confidence=correction_data.get("confidence"),
                    )
                    result.text_corrections.append(correction)

            # Handle enhanced summary format
            summary = analysis.get("summary")
            if isinstance(summary, dict):
                result.visual_summary = summary.get("overall_quality", str(summary))
            else:
                result.visual_summary = summary

            result.visual_score = analysis.get("overall_score")
            logger.info(
                "Visual analysis complete",
                url=url,
                issues=len(result.visual_issues),
                text_corrections=len(result.text_corrections),
                score=result.visual_score,
            )

        except Exception as e:
            error_msg = f"Screenshot analysis failed: {str(e)}"
            logger.error(error_msg, url=url)
            result.errors.append(error_msg)
