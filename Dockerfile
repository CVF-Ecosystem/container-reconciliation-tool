# Dockerfile for Container Inventory Reconciliation Tool V5.4
# Multi-stage build for production deployment

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install optional production dependencies
RUN pip install --no-cache-dir \
    gunicorn \
    uvicorn[standard] \
    python-multipart

# =============================================================================
# Stage 2: Production - Minimal runtime image
# =============================================================================
FROM python:3.11-slim as production

# Labels
LABEL maintainer="Tien-Tan Thuan Port"
LABEL version="5.4"
LABEL description="Container Inventory Reconciliation Tool"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_ENV=production \
    LOG_LEVEL=INFO

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup . .

# Create necessary directories
RUN mkdir -p /app/data_input /app/data_output /app/logs /app/reports && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose ports
# 8000 - REST API (FastAPI/uvicorn)
# 8501 - Streamlit Dashboard (optional)
EXPOSE 8000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from utils.health_check import run_health_check; run_health_check()" || exit 1

# Default command - Run API server
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# Stage 3: Development - Full development environment
# =============================================================================
FROM production as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-asyncio \
    black \
    flake8 \
    mypy \
    ipython

# Install GUI dependencies for local development
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

USER appuser

# Override command for development
CMD ["python", "-m", "pytest", "tests/", "-v"]

# =============================================================================
# Stage 4: GUI - Desktop application with tkinter
# =============================================================================
FROM python:3.11-slim as gui

LABEL description="Container Inventory Reconciliation Tool - GUI Version"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:0

WORKDIR /app

# Install system dependencies for GUI
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    libx11-6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/data_input /app/data_output /app/logs

# Default command - Run GUI
CMD ["python", "main.py"]
