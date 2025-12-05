# Multi-stage build for production optimization
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN pip install uv

# Set work directory
WORKDIR /app

# Copy UV configuration files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.12-slim AS production

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    DEBUG=false

# Install only runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy UV and virtual environment from base stage
COPY --from=base /usr/local/bin/uv /usr/local/bin/uv
COPY --from=base /app/.venv /app/.venv

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY worker/ ./worker/
COPY alembic.ini ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]