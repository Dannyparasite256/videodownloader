# VideoDL Pro — Architecture

## Overview

Industrial-grade Django video downloader using **clean architecture** layers:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Presentation | `templates/`, `apps/*/views.py`, `apps/api/` | HTTP/WS UI & REST |
| Application services | `services/` | Use-cases, orchestration |
| Domain models | `apps/*/models.py` | Entities & invariants |
| Repositories | `repositories/` | Data access |
| Engine | `apps/downloader/engine.py` | yt-dlp / FFmpeg isolation |
| Infrastructure | Redis, Celery, Postgres, Channels | Async & persistence |

## Request flow (download)

1. User pastes URL → `POST /metadata/` → `DownloadService.fetch_metadata` → yt-dlp extract
2. User confirms options → `POST /start/` → `DownloadService.create_download` → job `queued`
3. Celery worker runs `process_download` → `DownloadService.execute_download`
4. Progress hooks update DB + WebSocket group `download_{id}`
5. Client streams progress; on complete, file served via `/history/{id}/file/`

## Legal note

The engine **does not** bypass DRM or authentication walls. Operators must ensure users only download content they have rights to access, per platform ToS and copyright law.

## Scaling

- Horizontal web (Daphne/Uvicorn) behind Nginx
- Multiple Celery workers on `downloads` queue
- Redis for cache, broker, channel layer
- Postgres with indexes on status/user/platform
- Optional CDN for static assets
