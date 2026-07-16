# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libpq5 \
    nodejs \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY . /app

RUN mkdir -p /app/media/downloads /app/media/thumbnails /app/media/avatars /app/staticfiles /app/logs \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Collect static at build time so WhiteNoise always has a full manifest
# (includes js/theme-boot.js, css/app.css, etc.)
ENV DJANGO_SETTINGS_MODULE=config.settings \
    DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY=build-time-only-not-for-runtime \
    DATABASE_URL=sqlite:////tmp/build.sqlite3
RUN python manage.py collectstatic --noinput \
    && chown -R appuser:appuser /app/staticfiles

# Ensure start scripts are executable (Render dockerCommand uses bash)
RUN chmod +x /app/scripts/*.sh 2>/dev/null || true \
    && chown -R appuser:appuser /app

USER appuser

# Render injects PORT; default 8000 for local Docker
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f "http://127.0.0.1:${PORT:-8000}/api/v1/health/" || exit 1

# Default: web process (Render overrides with dockerCommand in render.yaml)
CMD ["bash", "scripts/render_start_web.sh"]
