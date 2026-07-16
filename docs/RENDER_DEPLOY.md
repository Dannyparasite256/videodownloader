# Deploy VideoDL Pro on Render

This project is configured for **Render** with Docker (includes FFmpeg),
PostgreSQL, Redis, a web service, and a Celery worker.

## Architecture on Render

| Service | Role |
|---------|------|
| `videodl-web` | Django + Daphne + **downloads** (HTTP, WebSockets, FFmpeg) |
| `videodl-db` | PostgreSQL |
| `videodl-redis` | Redis (cache, Channels, Celery broker) |
| Disk `/var/data` | Persistent downloads/media |

**Why no separate worker by default?**  
Render disks **cannot be shared** between two services. If Celery ran on a different service, files would be saved where the web app cannot serve them.  
This setup uses `CELERY_TASK_ALWAYS_EAGER=True` so downloads run on the **web** instance (background threads) and files stay on `/var/data`.

---

## Method A — Blueprint (recommended)

### 1. Push code to GitHub
Repo must include `render.yaml` on `main` (already in this project).

### 2. Create Blueprint on Render
1. Go to [https://dashboard.render.com](https://dashboard.render.com)
2. Sign in with GitHub
3. **New** → **Blueprint**
4. Connect `Dannyparasite256/videodownloader` (or your fork)
5. Branch: `main`
6. Render reads `render.yaml` and shows services
7. Click **Apply**

### 3. Wait for first deploy
- Postgres + Redis provision first  
- Web and worker build Docker image (includes `collectstatic` + FFmpeg)  
- Free web services may take a few minutes; first request can be slow (cold start)

### 4. Create admin user
1. Dashboard → **videodl-web** → **Shell**
2. Run:

```bash
python manage.py createsuperuser
```

### 5. Open the site
- Dashboard → **videodl-web** → copy the URL (`https://videodl-web-xxxx.onrender.com`)
- Health: `https://YOUR-URL/api/v1/health/`
- Admin: `https://YOUR-URL/admin/`

### 6. Test a download
1. Open the site  
2. Paste a **public** video URL  
3. Analyze → Download  
4. Progress should move (downloads run on the web service)

---

## Method B — Manual setup (no Blueprint)

### 1. PostgreSQL
**New** → **PostgreSQL** → name `videodl-db` → create  
Copy **Internal Database URL**.

### 2. Redis
**New** → **Key Value** (Redis) → name `videodl-redis` → create  
Copy **Internal Redis URL**.

### 3. Web service
**New** → **Web Service** → connect GitHub repo  

| Setting | Value |
|---------|--------|
| Runtime | **Docker** |
| Branch | `main` |
| Dockerfile path | `./Dockerfile` |
| Docker command | `bash scripts/render_start_web.sh` |
| Health check path | `/api/v1/health/` |
| Plan | Free or Starter |

**Environment variables:**

| Key | Value |
|-----|--------|
| `RENDER` | `true` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | Generate (or Render generate) |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` |
| `DATABASE_URL` | From Postgres (link env group or paste) |
| `REDIS_URL` | From Redis |
| `CELERY_BROKER_URL` | Same as `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | Same as `REDIS_URL` |
| `CHANNELS_REDIS_URL` | Same as `REDIS_URL` |
| `CELERY_TASK_ALWAYS_EAGER` | `False` |
| `DOWNLOAD_ROOT` | `/var/data/downloads` |
| `MEDIA_ROOT` | `/var/data/media` |

**Disk (recommended):**  
Add disk mount path `/var/data`, size 1 GB+

### 4. Background Worker
**New** → **Background Worker** → same repo, Docker  

| Setting | Value |
|---------|--------|
| Docker command | `bash scripts/render_start_worker.sh` |
| Same env vars as web | (use **Environment Group** to share) |
| Same disk `/var/data` | so files written by worker are visible |

### 5. Deploy both → createsuperuser in web Shell

---

## Environment reference

| Variable | Required | Notes |
|----------|----------|--------|
| `DJANGO_SECRET_KEY` | Yes | Auto-generated in blueprint |
| `DJANGO_DEBUG` | Yes | Must be `False` |
| `DATABASE_URL` | Yes | From Render Postgres |
| `REDIS_URL` | Yes | From Render Redis |
| `CELERY_*` | Recommended | Same Redis URL |
| `CELERY_TASK_ALWAYS_EAGER` | Yes for this setup | `True` = downloads on web (required without shared disk) |
| `DJANGO_ALLOWED_HOSTS` | Yes | `.onrender.com` is enough |
| `RENDER` | Auto | Set `true` if needed |
| `DOWNLOAD_ROOT` / `MEDIA_ROOT` | Recommended | `/var/data/...` with disk |

Settings auto-detect Render via `RENDER_EXTERNAL_HOSTNAME` and configure HTTPS, hosts, and CSRF.

---

## After every code update

```text
git push origin main
```

Render auto-deploys if **Auto-Deploy** is on.  
Or: Dashboard → Manual Deploy → **Deploy latest commit**.

---

## Common issues

| Symptom | Fix |
|---------|-----|
| Deploy fails on build | Check build logs; ensure Docker runtime, not Python native |
| `DisallowedHost` | Set `DJANGO_ALLOWED_HOSTS=.onrender.com` |
| CSRF failed | Site is HTTPS; app sets CSRF from Render URL automatically after redeploy |
| Downloads stuck **queued** | Ensure `CELERY_TASK_ALWAYS_EAGER=True` on web; check web logs |
| Progress never moves | Check **Logs** on videodl-web for yt-dlp/FFmpeg errors |
| Files disappear after redeploy | Attach persistent **disk** at `/var/data` |
| Free tier sleeps | First request after idle is slow; upgrade plan to avoid |
| Redis/Postgres free unavailable | Upgrade those services to **Starter** (Render plan changes) |
| Blueprint fails on Redis free | Create Redis as **Starter**, then link `REDIS_URL` manually |

---

## Cost note

Render free tiers change over time. You typically need:

- Web (free or starter) + **disk**  
- Postgres (free or starter)  
- Redis (often **Starter** / paid)  

Scale later with a dedicated Celery worker + S3/R2 for shared media.

---

## Custom domain (optional)

1. Web service → **Settings** → **Custom Domains** → add domain  
2. Add DNS records Render shows  
3. Add your domain to `DJANGO_ALLOWED_HOSTS` (e.g. `yourdomain.com,.onrender.com`)  
4. Redeploy  

HTTPS is automatic on Render.
