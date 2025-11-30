# Multi-stage Dockerfile for RAG Service
# Optimized for layer caching - dependencies are installed before source code

# =========================
# Base stage with system deps (shared by builder and dev)
# =========================
FROM python:3.11-slim AS base-deps

# Install common system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry (cached layer)
RUN pip install poetry==1.7.1

# =========================
# Builder stage (Python deps only)
# =========================
FROM base-deps AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Configure Poetry to use a project-local virtualenv
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Set work directory
WORKDIR /app

# Copy ONLY dependency files first (for better caching)
COPY pyproject.toml poetry.lock* ./

# Install only production dependencies into .venv (cached if deps unchanged)
RUN poetry install --only=main --no-root && rm -rf "$POETRY_CACHE_DIR"

# Download NLTK data (cached layer)
RUN .venv/bin/python -m nltk.downloader -d /app/nltk_data punkt punkt_tab averaged_perceptron_tagger averaged_perceptron_tagger_eng

# =========================
# Development stage (keeps Poetry + dev deps)
# =========================
FROM base-deps AS development

# Dev environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install additional dev system dependencies (separate layer for caching)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    libreoffice-core \
    # Playwright/Chromium dependencies
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
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Configure Poetry (dev image can use global env)
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=0 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Copy ONLY dependency files first (cached layer)
COPY pyproject.toml poetry.lock* ./

# Install dependencies including dev (cached if deps unchanged)
RUN poetry install --with dev --no-root && rm -rf "$POETRY_CACHE_DIR"

# Install Playwright browsers (cached layer - only re-runs if deps change)
RUN playwright install chromium && playwright install-deps chromium

# Download NLTK data (cached layer)
RUN python -m nltk.downloader -d /app/nltk_data punkt punkt_tab averaged_perceptron_tagger averaged_perceptron_tagger_eng
ENV NLTK_DATA=/app/nltk_data

# Create uploads directory
RUN mkdir -p /app/uploads

# NOW copy source code (this layer changes frequently, but deps are cached above)
COPY . .

# Expose port
EXPOSE 8082

# Default command for development (with reload)
CMD ["poetry", "run", "uvicorn", "src.rag_service.main:app", "--host", "0.0.0.0", "--port", "8082", "--reload"]

# =========================
# Production runtime stage
# =========================
FROM python:3.11-slim AS production

# Runtime environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install runtime system dependencies including OCR/office tools and Playwright deps
# This layer is cached and only rebuilds when apt packages change
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    libmagic1 \
    libreoffice-core \
    # Playwright/Chromium dependencies
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
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /var/cache/apt/*

# Set home and cache directories for non-root user
ENV HOME=/home/rag XDG_CACHE_HOME=/home/rag/.cache

# Create non-root user
RUN groupadd -r rag && useradd -r -g rag rag && \
    mkdir -p /home/rag/.cache /app/uploads /app/logs && \
    chown -R rag:rag /home/rag /app

# Set work directory
WORKDIR /app

# Copy virtualenv from builder (cached - only changes when deps change)
COPY --from=builder --chown=rag:rag /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy NLTK data from builder (cached)
COPY --from=builder --chown=rag:rag /app/nltk_data /app/nltk_data
ENV NLTK_DATA=/app/nltk_data

# Install Playwright browsers BEFORE copying source code (cached layer)
# This ensures browser download is cached even when source changes
RUN playwright install chromium && playwright install-deps chromium \
    && chown -R rag:rag /home/rag/.cache

# NOW copy source code (this changes frequently but all heavy deps are cached above)
COPY --chown=rag:rag . .

# Switch to non-root user
USER rag

# Expose port
EXPOSE 8082

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

# Default command for production: run via uvicorn directly (no Poetry at runtime)
CMD ["uvicorn", "src.rag_service.main:app", "--host", "0.0.0.0", "--port", "8082", "--workers", "4"]
