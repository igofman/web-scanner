"""Configuration settings for the web scanner."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Crawler settings
    max_depth: int = Field(default=3, description="Maximum crawl depth")
    max_pages: int = Field(default=100, description="Maximum pages to crawl")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    concurrent_requests: int = Field(default=3, description="Max concurrent browser pages")
    respect_robots_txt: bool = Field(default=True, description="Respect robots.txt")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent string (realistic browser UA)",
    )

    # Playwright/Browser settings
    page_load_timeout: int = Field(
        default=30000,
        description="Page load timeout in milliseconds",
    )
    js_wait_timeout: int = Field(
        default=3000,
        description="Additional wait time for JavaScript rendering (ms)",
    )
    wait_for_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to wait for before considering page loaded",
    )
    max_retries: int = Field(
        default=2,
        description="Maximum retries for failed page loads",
    )

    # Storage settings
    output_dir: Path = Field(default=Path("./data"), description="Output directory for data")
    reports_dir: Path = Field(default=Path("./reports"), description="Reports directory")

    # Screenshot settings
    screenshot_width: int = Field(default=1920, description="Screenshot viewport width")
    screenshot_height: int = Field(default=1080, description="Screenshot viewport height")
    screenshot_full_page: bool = Field(default=True, description="Capture full page screenshot")

    # Analyzer settings
    grammar_language: str = Field(default="en-US", description="Language for grammar checking")
    check_external_links: bool = Field(default=False, description="Check external links")

    # OCR settings
    tesseract_lang: str = Field(default="eng", description="Tesseract OCR language")

    model_config = {"env_prefix": "SCANNER_", "env_file": ".env"}


settings = Settings()
