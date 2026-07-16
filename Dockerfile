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

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/api/v1/health/ || exit 1

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
