# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Cloudflare WARP tools (userspace SOCKS) — routes yt-dlp off blocked datacenter IPs
ARG WGCF_VERSION=2.2.22
ARG WIREPROXY_VERSION=1.0.9

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    unzip \
    libpq5 \
    nodejs \
    iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    # Deno is yt-dlp's default JS runtime for YouTube EJS challenges
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version \
    # wgcf: generate free WARP WireGuard credentials
    && curl -fsSL -o /usr/local/bin/wgcf \
      "https://github.com/ViRb3/wgcf/releases/download/v${WGCF_VERSION}/wgcf_${WGCF_VERSION}_linux_amd64" \
    && chmod +x /usr/local/bin/wgcf \
    # wireproxy: userspace WireGuard → local SOCKS5 (no root/NET_ADMIN)
    && curl -fsSL -o /tmp/wireproxy.tgz \
      "https://github.com/pufferffish/wireproxy/releases/download/v${WIREPROXY_VERSION}/wireproxy_linux_amd64.tar.gz" \
    && tar -xzf /tmp/wireproxy.tgz -C /tmp \
    && mv /tmp/wireproxy /usr/local/bin/wireproxy \
    && chmod +x /usr/local/bin/wireproxy \
    && rm -f /tmp/wireproxy.tgz \
    && wgcf --help >/dev/null \
    && wireproxy -h >/dev/null 2>&1 || true


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

RUN mkdir -p /app/media/downloads /app/media/thumbnails /app/media/avatars /app/staticfiles /app/logs /app/warp \
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
    && chown -R appuser:appuser /app /app/warp

USER appuser

# Render injects PORT; default 8000 for local Docker
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f "http://127.0.0.1:${PORT:-8000}/api/v1/health/" || exit 1

# Default: web process (Render overrides with dockerCommand in render.yaml)
CMD ["bash", "scripts/render_start_web.sh"]
