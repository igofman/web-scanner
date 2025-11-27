# Multi-stage build for Python web scanner
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set up working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Install dependencies using uv with pip
# First install the build backend, then the package
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install --system hatchling && \
    uv pip install --system .

# Install Playwright browsers (need to install deps in builder too)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

RUN playwright install chromium

# Final stage
FROM python:3.11-slim

# Install system dependencies for Playwright and Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    # Java for LanguageTool
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy source code
COPY src/ src/
COPY pyproject.toml .

# Set up environment
ENV PYTHONPATH="/app/src"

# Create data directories
RUN mkdir -p /app/data /app/reports

# Set default environment variables
ENV SCANNER_OUTPUT_DIR=/app/data
ENV SCANNER_REPORTS_DIR=/app/reports

# Entry point
ENTRYPOINT ["python", "-m", "web_scanner.cli"]
CMD ["--help"]
