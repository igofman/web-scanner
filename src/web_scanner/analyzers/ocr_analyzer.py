"""OCR analyzer for extracting and analyzing text from screenshots."""

import asyncio
from pathlib import Path

import structlog
from PIL import Image

from ..config import settings
from ..models import OCRIssue
from .base import BaseAnalyzer
from .grammar_analyzer import GrammarAnalyzer

logger = structlog.get_logger()


class OCRAnalyzer(BaseAnalyzer):
    """Extracts text from screenshots using OCR and analyzes for issues."""

    def __init__(self):
        self._grammar_analyzer = GrammarAnalyzer()
        self._tesseract_lang = settings.tesseract_lang

    async def start(self) -> None:
        """Initialize resources."""
        await self._grammar_analyzer.start()

    async def stop(self) -> None:
        """Clean up resources."""
        await self._grammar_analyzer.stop()

    def _extract_text_from_image(self, image_path: Path) -> tuple[str, float]:
        """
        Extract text from image using Tesseract OCR.

        Returns:
            Tuple of (extracted_text, average_confidence)
        """
        import pytesseract

        try:
            image = Image.open(image_path)

            # Get detailed data including confidence
            data = pytesseract.image_to_data(
                image,
                lang=self._tesseract_lang,
                output_type=pytesseract.Output.DICT,
            )

            # Extract text and calculate average confidence
            words = []
            confidences = []

            for i, word in enumerate(data["text"]):
                conf = int(data["conf"][i])
                if word.strip() and conf > 0:  # Skip empty strings and low confidence
                    words.append(word)
                    confidences.append(conf)

            text = " ".join(words)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            return text, avg_confidence / 100  # Normalize to 0-1

        except Exception as e:
            logger.error("OCR extraction failed", image=str(image_path), error=str(e))
            return "", 0.0

    async def analyze(self, screenshot_path: Path) -> list[OCRIssue]:
        """
        Analyze a screenshot for text issues.

        Args:
            screenshot_path: Path to the screenshot image.

        Returns:
            List of OCR issues found.
        """
        await self.start()

        issues = []

        try:
            # Extract text from image (blocking operation)
            loop = asyncio.get_event_loop()
            extracted_text, confidence = await loop.run_in_executor(
                None, self._extract_text_from_image, screenshot_path
            )

            if not extracted_text or confidence < 0.3:
                logger.debug(
                    "Low confidence or no text extracted",
                    path=str(screenshot_path),
                    confidence=confidence,
                )
                return issues

            # Check for grammar/spelling issues in extracted text
            grammar_issues = await self._grammar_analyzer.analyze_text(
                extracted_text, source_url=str(screenshot_path)
            )

            for grammar_issue in grammar_issues:
                ocr_issue = OCRIssue(
                    screenshot_path=str(screenshot_path),
                    extracted_text=grammar_issue.context,
                    issue_type="grammar",
                    description=grammar_issue.message,
                    confidence=confidence,
                )
                issues.append(ocr_issue)

            # Check for common visual text issues
            visual_issues = self._check_visual_text_issues(extracted_text, screenshot_path)
            issues.extend(visual_issues)

            logger.info(
                "OCR analysis complete",
                path=str(screenshot_path),
                text_length=len(extracted_text),
                issues_found=len(issues),
            )

        except Exception as e:
            logger.error("OCR analysis failed", path=str(screenshot_path), error=str(e))

        return issues

    def _check_visual_text_issues(self, text: str, screenshot_path: Path) -> list[OCRIssue]:
        """Check for common visual text issues."""
        issues = []

        # Check for placeholder text that shouldn't be visible
        placeholder_patterns = [
            ("Lorem ipsum", "Placeholder text detected"),
            ("TODO:", "TODO marker visible to users"),
            ("FIXME:", "FIXME marker visible to users"),
            ("XXX", "XXX marker visible to users"),
            ("[object Object]", "JavaScript object rendered as text"),
            ("undefined", "Undefined value displayed"),
            ("null", "Null value displayed"),
            ("NaN", "NaN value displayed"),
        ]

        text_lower = text.lower()
        for pattern, description in placeholder_patterns:
            if pattern.lower() in text_lower:
                issues.append(
                    OCRIssue(
                        screenshot_path=str(screenshot_path),
                        extracted_text=pattern,
                        issue_type="placeholder_text",
                        description=description,
                        confidence=0.9,
                    )
                )

        # Check for common encoding issues
        encoding_issues = ["â€", "Ã¢", "Ã©", "â€™", "â€œ"]
        for encoding_issue in encoding_issues:
            if encoding_issue in text:
                issues.append(
                    OCRIssue(
                        screenshot_path=str(screenshot_path),
                        extracted_text=encoding_issue,
                        issue_type="encoding_issue",
                        description="Possible character encoding problem detected",
                        confidence=0.8,
                    )
                )
                break  # Only report once

        return issues

    async def analyze_batch(self, screenshot_paths: list[Path]) -> list[OCRIssue]:
        """Analyze multiple screenshots."""
        await self.start()

        all_issues = []
        for path in screenshot_paths:
            issues = await self.analyze(path)
            all_issues.extend(issues)

        return all_issues
