# Web Scanner

A Python platform for scanning websites, extracting content (HTML, text, screenshots), and analyzing for issues like grammar mistakes, broken links, and visual text problems.

## Features

- **Recursive Crawling**: Discovers and crawls all pages within a website
- **Content Extraction**:
  - Raw HTML preservation
  - Clean text extraction
  - Full-page screenshots
- **Analysis**:
  - Grammar and spelling checking using LanguageTool
  - Broken link detection
  - OCR-based text analysis from screenshots
- **Organized Storage**: Creates structured folders for each scan

## Project Structure

```
web-scanner/
├── src/web_scanner/
│   ├── crawler/         # Recursive web crawler
│   ├── extractors/      # HTML, text, and screenshot extractors
│   ├── analyzers/       # Grammar, link, and OCR analyzers
│   ├── storage/         # Data organization and persistence
│   ├── utils/           # Logging and utilities
│   ├── cli.py           # Command-line interface
│   ├── config.py        # Configuration settings
│   ├── models.py        # Data models
│   └── orchestrator.py  # Main workflow coordinator
├── data/                # Extracted data (created on run)
├── reports/             # Analysis reports (created on run)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Quick Start with Docker

### Build and Run

```bash
# Build the Docker image
docker-compose build

# Scan a website
docker-compose run --rm web-scanner scan https://example.com --depth 2 --max-pages 50

# View help
docker-compose run --rm web-scanner --help
```

### Example Commands

```bash
# Full scan with all analyzers
docker-compose run --rm web-scanner scan https://example.com

# Quick scan without screenshots (faster)
docker-compose run --rm web-scanner scan https://example.com --no-screenshots

# Deep crawl with more pages
docker-compose run --rm web-scanner scan https://example.com --depth 5 --max-pages 200

# Skip specific analyzers
docker-compose run --rm web-scanner scan https://example.com --no-grammar --no-ocr
```

## Local Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Tesseract OCR (for OCR analysis)
- Java Runtime (for LanguageTool)

### Install with uv

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Install Playwright browsers
playwright install chromium
```

### Install System Dependencies

**macOS:**
```bash
brew install tesseract tesseract-lang
brew install --cask temurin  # Java runtime
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng default-jre-headless
```

### Run Locally

```bash
# Run the scanner
python -m web_scanner.cli scan https://example.com

# Or use the installed command
web-scanner scan https://example.com --depth 2
```

## Configuration

Configuration can be set via environment variables or a `.env` file:

```bash
# Copy example config
cp .env.example .env
```

### Available Options

| Variable | Default | Description |
|----------|---------|-------------|
| `SCANNER_MAX_DEPTH` | 3 | Maximum crawl depth |
| `SCANNER_MAX_PAGES` | 100 | Maximum pages to crawl |
| `SCANNER_CONCURRENT_REQUESTS` | 5 | Concurrent HTTP requests |
| `SCANNER_OUTPUT_DIR` | ./data | Output directory |
| `SCANNER_REPORTS_DIR` | ./reports | Reports directory |
| `SCANNER_SCREENSHOT_FULL_PAGE` | true | Capture full page |
| `SCANNER_GRAMMAR_LANGUAGE` | en-US | Grammar check language |
| `SCANNER_CHECK_EXTERNAL_LINKS` | false | Check external links |

## Output Structure

Each scan creates a timestamped folder:

```
data/
└── example_com_20240115_143022/
    ├── html/              # Raw HTML files
    ├── text/              # Extracted text files
    ├── screenshots/       # Page screenshots
    └── metadata/
        ├── crawl_metadata.json
        └── extraction_index.json

reports/
└── example_com_20240115_143022/
    ├── analysis_report.json
    └── summary.txt
```

## CLI Reference

```
web-scanner scan [OPTIONS] URL

Arguments:
  URL  The URL to scan [required]

Options:
  -d, --depth INTEGER      Maximum crawl depth [default: 3]
  -m, --max-pages INTEGER  Maximum pages to crawl [default: 100]
  -o, --output PATH        Output directory
  --no-screenshots         Skip screenshot capture
  --no-grammar             Skip grammar analysis
  --no-links               Skip broken link analysis
  --no-ocr                 Skip OCR analysis
  -v, --verbose            Enable verbose logging
  --help                   Show this message and exit
```

## Extending

### Adding Custom Extractors

Create a new extractor in `src/web_scanner/extractors/`:

```python
from .base import BaseExtractor

class MyExtractor(BaseExtractor):
    async def extract(self, page: CrawledPage) -> Path | None:
        # Your extraction logic
        pass
```

### Adding Custom Analyzers

Create a new analyzer in `src/web_scanner/analyzers/`:

```python
from .base import BaseAnalyzer

class MyAnalyzer(BaseAnalyzer):
    async def analyze(self, data: Any) -> list[Any]:
        # Your analysis logic
        pass
```

## License

MIT License
