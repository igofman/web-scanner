"""OpenRouter API client for AI-powered analysis."""

import base64
from pathlib import Path
from typing import Any

import httpx
import structlog

from ..config import settings

logger = structlog.get_logger()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        vision_model: str | None = None,
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.ai_model
        self.vision_model = vision_model or settings.ai_vision_model
        self._client: httpx.AsyncClient | None = None

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is required. Set SCANNER_OPENROUTER_API_KEY "
                "environment variable or pass api_key parameter."
            )

    async def start(self) -> None:
        """Initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/web-scanner",
                    "X-Title": "Web Scanner AI Analysis",
                    "Content-Type": "application/json",
                },
            )
            logger.info("OpenRouter client initialized", model=self.model)

    async def stop(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("OpenRouter client closed")

    async def _make_request(
        self,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Make a request to OpenRouter API."""
        if self._client is None:
            await self.start()

        payload = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = await self._client.post(OPENROUTER_API_URL, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenRouter API error",
                status_code=e.response.status_code,
                response=e.response.text,
            )
            raise
        except Exception as e:
            logger.error("OpenRouter request failed", error=str(e))
            raise

    async def analyze_text(
        self,
        text: str,
        analysis_type: str = "general",
        custom_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze text content for issues.

        Args:
            text: The text content to analyze
            analysis_type: Type of analysis (grammar, content, seo, accessibility)
            custom_prompt: Optional custom prompt to use

        Returns:
            Analysis results with issues found
        """
        if custom_prompt:
            system_prompt = custom_prompt
        else:
            system_prompt = self._get_text_analysis_prompt(analysis_type)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze the following text:\n\n{text[:15000]}"},
        ]

        result = await self._make_request(messages)
        return self._parse_response(result)

    async def analyze_html(
        self,
        html: str,
        url: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze HTML content for issues.

        Args:
            html: The HTML content to analyze
            url: Optional URL for context

        Returns:
            Analysis results with issues found
        """
        system_prompt = """You are an expert web developer and accessibility specialist.
Analyze the provided HTML code and identify issues in these categories:

1. **HTML Errors**: Invalid markup, unclosed tags, deprecated elements, missing required attributes
2. **Accessibility Issues**: Missing alt text, improper heading hierarchy, missing ARIA labels, poor contrast indicators
3. **SEO Problems**: Missing meta tags, improper heading structure, missing semantic HTML
4. **Best Practice Violations**: Inline styles, missing doctype, improper nesting
5. **Security Concerns**: Inline scripts, missing CSP indicators, potentially unsafe patterns

For each issue found, provide:
- severity: "critical", "warning", or "info"
- category: one of the categories above
- description: clear explanation of the issue
- location: where in the HTML (tag/element)
- suggestion: how to fix it

Respond in JSON format:
{
  "issues": [
    {
      "severity": "warning",
      "category": "Accessibility Issues",
      "description": "Image missing alt attribute",
      "location": "<img src='...'> on line ~X",
      "suggestion": "Add descriptive alt text: alt='description of image'"
    }
  ],
  "summary": "Brief summary of overall HTML quality"
}"""

        context = f"URL: {url}\n\n" if url else ""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context}Analyze this HTML:\n\n{html[:20000]}"},
        ]

        result = await self._make_request(messages)
        return self._parse_response(result)

    async def analyze_image(
        self,
        image_path: Path | str,
        page_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a screenshot image for visual issues.

        Args:
            image_path: Path to the screenshot image
            page_url: Optional URL for context

        Returns:
            Analysis results with visual issues found
        """
        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning("Image not found", path=str(image_path))
            return {"issues": [], "error": "Image file not found"}

        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

        system_prompt = """You are a multimodal expert in UI/UX, accessibility, and linguistics.
Analyze the provided SCREENSHOT image and identify issues in these categories:

1. **Visual/Layout Issues**: Misalignment, inconsistent spacing, overlap, clipping, crowding, poor hierarchy, awkward balance.
2. **Accessibility & Readability**: Insufficient color contrast, tiny tap targets, low legibility, non-descriptive labels, ambiguous icons, motion/flash risks.
3. **Typography**: Inconsistent fonts, sizes, weights, line-height, letter-spacing, improper casing, widows/orphans, stretched/distorted text.
4. **Content & Grammar**: Spelling, grammar, punctuation, tone, clarity, consistency; awkward microcopy; UI label mismatches; duplicated or conflicting text.
5. **Localization & Formatting**: Wrong locale conventions (date/number/currency), pluralization, missing diacritics/RTL handling, clipped translations.
6. **Usability & Interaction Clarity**: Unclear CTAs, competing primary actions, hidden affordances, misleading states, non-standard patterns that hinder understanding.
7. **Branding & Consistency**: Off-brand colors/spacing/illustrations, inconsistent iconography or component styles.
8. **Potential Risk/Compliance**: Exposed PII in screenshot, deceptive patterns (dark patterns), sensitive content.

For each issue found, provide:
- severity: "critical", "warning", or "info"
- category: one of the categories above
- description: clear explanation of the issue
- location: where in the screenshot (named area and/or bounding box)
- bbox: normalized bounding box of the problematic region as [x, y, w, h] in 0..1 coordinates (omit if not applicable)
- evidence: short OCR text snippet or visual cue observed (if relevant)
- suggestion: how to fix it
- confidence: integer 1-5

Additionally, extract and correct any text with language issues:
Return a list of "text_corrections" with:
- original: the exact text as seen (or best-effort OCR)
- correction: proposed corrected text
- explanation: brief reason (grammar rule, tone, clarity)
- bbox: normalized bounding box [x, y, w, h] where the text appears (if known)
- confidence: 1-5

Assumptions & Notes:
- If a region is unreadable/blurred, note this and lower confidence.
- If you are uncertain whether an element is interactive, say so and explain why.
- Contrast checks may be approximate; flag as "estimated contrast" when sampled from pixels.
- Do NOT invent unseen content.

Respond in JSON format ONLY:
{
  "issues": [
    {
      "severity": "warning",
      "category": "Accessibility & Readability",
      "description": "CTA text has low contrast against background.",
      "location": "Primary button near bottom-right",
      "bbox": [0.72, 0.82, 0.22, 0.08],
      "evidence": "White #FFFFFF on light yellow ~#FFF3B0 (estimated).",
      "suggestion": "Increase contrast (e.g., darken background or use darker text to meet WCAG AA >= 4.5:1).",
      "confidence": 4
    }
  ],
  "text_corrections": [
    {
      "original": "You must login now!",
      "correction": "Please log in now.",
      "explanation": "'Log in' (verb) vs. 'login' (noun); softer UX tone.",
      "bbox": [0.28, 0.14, 0.44, 0.05],
      "confidence": 5
    }
  ],
  "summary": {
    "overall_quality": "Brief assessment of overall visual quality",
    "key_risks": ["List of main issues"],
    "wcag_notes": "Accessibility compliance notes",
    "counts": {
      "critical": 0,
      "warning": 0,
      "info": 0,
      "text_corrections": 0
    }
  },
  "overall_score": 8.5
}"""

        context = f"Page URL: {page_url}\n\n" if page_url else ""
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{context}Analyze this website screenshot for visual issues:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                        },
                    },
                ],
            },
        ]

        result = await self._make_request(messages, model=self.vision_model)
        return self._parse_response(result)

    def _get_text_analysis_prompt(self, analysis_type: str) -> str:
        """Get the appropriate system prompt for text analysis."""
        prompts = {
            "grammar": """You are an expert editor and proofreader.
Analyze the text for grammar, spelling, punctuation, and style issues.

For each issue found, provide:
- severity: "critical" (major errors), "warning" (minor issues), or "info" (style suggestions)
- category: "Grammar", "Spelling", "Punctuation", "Style", "Clarity"
- description: the specific issue
- original: the problematic text
- suggestion: the corrected version

Respond in JSON format:
{
  "issues": [...],
  "summary": "Brief summary of writing quality"
}""",
            "content": """You are a content quality analyst.
Analyze the text for content quality issues:
- Clarity and readability
- Consistency in tone and style
- Missing information or incomplete sections
- Redundant or duplicate content
- Factual inconsistencies

Respond in JSON format with issues and summary.""",
            "seo": """You are an SEO specialist.
Analyze the text for SEO optimization opportunities:
- Keyword usage and density
- Readability for web
- Meta content suggestions
- Content structure

Respond in JSON format with issues and summary.""",
            "general": """You are a comprehensive content analyst.
Analyze the text for:
1. Grammar, spelling, and punctuation errors
2. Clarity and readability issues
3. Content quality problems
4. Style inconsistencies

For each issue, provide severity, category, description, and suggestion.
Respond in JSON format:
{
  "issues": [
    {
      "severity": "warning",
      "category": "Grammar",
      "description": "Subject-verb agreement error",
      "original": "The data are...",
      "suggestion": "The data is..."
    }
  ],
  "summary": "Brief summary"
}""",
        }
        return prompts.get(analysis_type, prompts["general"])

    def _parse_response(self, response: dict) -> dict[str, Any]:
        """Parse the API response and extract the content."""
        try:
            content = response["choices"][0]["message"]["content"]

            # Try to extract JSON from the response
            import json
            import re

            # Try to find JSON in the response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # If no valid JSON, return the raw content
            return {
                "issues": [],
                "summary": content,
                "raw_response": content,
            }
        except (KeyError, IndexError) as e:
            logger.error("Failed to parse API response", error=str(e))
            return {"issues": [], "error": str(e)}

    async def __aenter__(self) -> "OpenRouterClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()
