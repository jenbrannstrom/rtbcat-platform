# RTBcat Creative Intelligence - Multi-stage Docker Build
# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Python dependencies
ARG INSTALL_AI_EXTRAS=false
COPY requirements.txt requirements-ai.txt ./
RUN mkdir -p /ms-playwright && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_AI_EXTRAS" = "true" ]; then \
      pip install --no-cache-dir -r requirements-ai.txt && \
      python -m playwright install chromium; \
    fi

# Stage 2: Runtime
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Create non-root user for security
RUN groupadd -r rtbcat && useradd -r -g rtbcat rtbcat

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /ms-playwright /ms-playwright
ENV PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install runtime dependencies (ffmpeg for video thumbnails, Chromium libs for AI extras)
ARG INSTALL_AI_EXTRAS=false
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    if [ "$INSTALL_AI_EXTRAS" = "true" ]; then \
      /opt/venv/bin/python -m playwright install-deps chromium; \
    fi && \
    rm -rf /var/lib/apt/lists/* && \
    chown -R rtbcat:rtbcat /ms-playwright

# Copy application code
COPY --chown=rtbcat:rtbcat . .

# Create data directory (matches production mount point)
RUN mkdir -p /home/rtbcat/.catscan && chown rtbcat:rtbcat /home/rtbcat/.catscan

# Build/runtime version metadata
ARG APP_VERSION=0.0.0
ARG GIT_SHA=unknown
ARG RELEASE_VERSION=0.0.0
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA} \
    RELEASE_VERSION=${RELEASE_VERSION} \
    UVICORN_WORKERS=1

# Switch to non-root user
USER rtbcat

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command: start API server (worker count configurable via UVICORN_WORKERS)
CMD ["sh", "-c", "exec python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]
