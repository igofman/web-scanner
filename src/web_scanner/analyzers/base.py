"""Base analyzer interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAnalyzer(ABC):
    """Abstract base class for all analyzers."""

    @abstractmethod
    async def analyze(self, data: Any) -> list[Any]:
        """
        Analyze the provided data and return a list of issues.

        Args:
            data: The data to analyze.

        Returns:
            List of issues found during analysis.
        """
        pass

    async def start(self) -> None:
        """Initialize any resources needed by the analyzer."""
        pass

    async def stop(self) -> None:
        """Clean up any resources used by the analyzer."""
        pass
