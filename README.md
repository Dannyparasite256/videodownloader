# VideoDL Pro

**Industrial-grade Django video downloader** with a premium glassmorphism UI, real-time WebSocket progress, Celery workers, REST API, and Docker deployment.

> **Legal:** Only download content you have the right to download. Respect platform Terms of Service and copyright law. This application does **not** bypass DRM or access controls.

---

## Features

- **Smart URL detection** via yt-dlp (YouTube, TikTok, Instagram, X, Vimeo, Reddit, SoundCloud, Bilibili, and any yt-dlp-supported site)
- Instant **metadata** (title, thumbnail, formats, subtitles, chapters)
- Download modes: video+audio, video only, audio only, playlist, subtitles, thumbnail
- Qualities up to **8K**, audio up to **320 kbps / lossless**, multiple containers
- **Live progress** (WebSocket + polling fallback): %, speed, ETA, stage
- Pause / resume / cancel / retry / re-download / favorites
- **Dashboard** with Chart.js analytics
- User accounts, API keys, JWT, optional Google/GitHub OAuth (django-allauth)
- REST API + **OpenAPI / Swagger** at `/api/docs/`
- Celery + Redis background jobs, cleanup & stats beat tasks
- Dark / light theme, accent colors, mobile-first Tailwind + Alpine.js + HTMX
- Docker Compose stack: web, worker, beat, Postgres, Redis, Nginx

---

## Quick start (local)

### Requirements

- Python 3.11+
- FFmpeg on `PATH`
- Optional: Redis, PostgreSQL (SQLite works for development)

```bash
# Clone / enter project
cd "django downloader"

# Virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt

# Environment
copy .env.example .env   # Windows
# cp .env.example .env   # Unix

# Migrations & superuser
python manage.py migrate
python manage.py createsuperuser

# Run ASGI server (HTTP + WebSockets)
daphne -b 0.0.0.0 -p 8000 config.asgi:application
# Or for quick dev without websockets reliability:
# python manage.py runserver
```

In another terminal (recommended for real downloads):

```bash
celery -A config worker -l info -Q celery,downloads,maintenance,analytics,notifications
```

Open **http://127.0.0.1:8000**

> Without a Celery worker, jobs stay in `queued`. For local smoke tests you can call `DownloadService().execute_download(job_id)` or run the worker above.

---

## Deploy on Render (recommended cloud)

This repo includes a **Render Blueprint** (`render.yaml`) for:

- Docker web (Daphne + FFmpeg)
- Celery worker
- PostgreSQL + Redis
- Persistent disk for downloads

**Guide:** [docs/RENDER_DEPLOY.md](docs/RENDER_DEPLOY.md)

Quick path: Render Dashboard → **New** → **Blueprint** → connect this GitHub repo → **Apply**.

Then open the web service **Shell** and run:

```bash
python manage.py createsuperuser
```

## Docker Compose (VPS / local production)

```bash
cp .env.example .env
# Set a strong DJANGO_SECRET_KEY and DJANGO_DEBUG=False for production

docker compose up --build -d
```

| Service | Port |
|---------|------|
| Nginx   | 80   |
| Web (direct) | 8000 |
| Postgres | 5432 (internal) |
| Redis | 6379 (internal) |

---

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/` | Health check |
| POST | `/api/v1/metadata/` | Extract metadata |
| GET/POST | `/api/v1/downloads/` | List / create jobs |
| POST | `/api/v1/downloads/{id}/pause/` | Pause |
| POST | `/api/v1/downloads/{id}/resume/` | Resume |
| POST | `/api/v1/downloads/{id}/cancel/` | Cancel |
| GET | `/api/v1/downloads/{id}/progress/` | Progress JSON |
| GET | `/api/v1/downloads/{id}/file/` | Download file |
| GET | `/api/v1/stats/` | User statistics |
| POST | `/api/v1/auth/token/` | JWT obtain |

Interactive docs: `/api/docs/` (Swagger) · `/api/redoc/`

WebSocket: `ws://host/ws/downloads/<uuid>/`

---

## Project layout

```
apps/           # Django apps (accounts, downloads, downloader, api, …)
services/       # Application service layer
repositories/   # Data access
config/         # Settings, ASGI, Celery
templates/      # Premium UI
static/         # CSS / JS / PWA manifest
docker/         # Nginx config
tests/          # Unit & API tests
docs/           # Architecture notes
```

---

## Tests

```bash
pytest -q
python manage.py check
```

---

## Configuration

See `.env.example` for all variables: database, Redis, OAuth, Sentry, download limits, quotas.

---

## Production checklist

- [ ] Strong `DJANGO_SECRET_KEY`
- [ ] `DJANGO_DEBUG=False`
- [ ] HTTPS + `SECURE_SSL_REDIRECT=True`
- [ ] Managed Postgres & Redis
- [ ] FFmpeg on workers
- [ ] Celery worker + beat running
- [ ] Volume backups for `media/`
- [ ] Sentry DSN (optional)
- [ ] Rate limits tuned for your traffic

---

## License & ethics

Use responsibly. You are responsible for compliance with applicable laws and platform terms. This software is provided for legitimate personal and authorized use cases only.
