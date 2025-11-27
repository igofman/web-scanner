"""Grammar analyzer using LanguageTool."""

import asyncio
from pathlib import Path

import aiofiles
import structlog

from ..config import settings
from ..models import GrammarIssue
from .base import BaseAnalyzer

logger = structlog.get_logger()


class GrammarAnalyzer(BaseAnalyzer):
    """Analyzes text content for grammar and spelling issues."""

    def __init__(self):
        self._tool = None
        self._language = settings.grammar_language

    async def start(self) -> None:
        """Initialize LanguageTool."""
        if self._tool is None:
            # LanguageTool initialization is blocking, run in executor
            loop = asyncio.get_event_loop()
            self._tool = await loop.run_in_executor(None, self._init_tool)
            logger.info("Grammar analyzer initialized", language=self._language)

    def _init_tool(self):
        """Initialize LanguageTool (blocking)."""
        import language_tool_python
        return language_tool_python.LanguageTool(self._language)

    async def stop(self) -> None:
        """Clean up LanguageTool."""
        if self._tool:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._tool.close)
            self._tool = None

    async def analyze(self, text_path: Path) -> list[GrammarIssue]:
        """
        Analyze text file for grammar issues.

        Args:
            text_path: Path to the text file to analyze.

        Returns:
            List of grammar issues found.
        """
        await self.start()

        try:
            async with aiofiles.open(text_path, "r", encoding="utf-8") as f:
                content = await f.read()

            # Skip metadata header (first few lines until the separator)
            if "---" in content:
                parts = content.split("-" * 80, 1)
                if len(parts) > 1:
                    content = parts[1].strip()

            # Run grammar check in executor (blocking operation)
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, self._tool.check, content)

            issues = []
            for match in matches:
                # Skip certain rules that are too noisy
                if match.ruleId in ("WHITESPACE_RULE", "COMMA_PARENTHESIS_WHITESPACE"):
                    continue

                context_start = max(0, match.offset - 20)
                context_end = min(len(content), match.offset + match.errorLength + 20)
                context = content[context_start:context_end]

                issue = GrammarIssue(
                    message=match.message,
                    context=context,
                    suggestions=match.replacements[:5] if match.replacements else [],
                    offset=match.offset,
                    length=match.errorLength,
                    rule_id=match.ruleId,
                    category=match.category,
                )
                issues.append(issue)

            logger.info(
                "Grammar analysis complete",
                file=str(text_path),
                issues_found=len(issues),
            )

            return issues

        except Exception as e:
            logger.error("Grammar analysis failed", file=str(text_path), error=str(e))
            return []

    async def analyze_text(self, text: str, source_url: str = "") -> list[GrammarIssue]:
        """
        Analyze raw text for grammar issues.

        Args:
            text: The text to analyze.
            source_url: Optional source URL for logging.

        Returns:
            List of grammar issues found.
        """
        await self.start()

        try:
            loop = asyncio.get_event_loop()
            matches = await loop.run_in_executor(None, self._tool.check, text)

            issues = []
            for match in matches:
                if match.ruleId in ("WHITESPACE_RULE", "COMMA_PARENTHESIS_WHITESPACE"):
                    continue

                context_start = max(0, match.offset - 20)
                context_end = min(len(text), match.offset + match.errorLength + 20)
                context = text[context_start:context_end]

                issue = GrammarIssue(
                    message=match.message,
                    context=context,
                    suggestions=match.replacements[:5] if match.replacements else [],
                    offset=match.offset,
                    length=match.errorLength,
                    rule_id=match.ruleId,
                    category=match.category,
                )
                issues.append(issue)

            logger.info(
                "Grammar analysis complete",
                source=source_url or "raw_text",
                issues_found=len(issues),
            )

            return issues

        except Exception as e:
            logger.error("Grammar analysis failed", error=str(e))
            return []
