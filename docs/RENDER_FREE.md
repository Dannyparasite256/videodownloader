# Render free tier — what works

This project is tuned for **Render free web** (Docker, SQLite, no Redis, no disk).

## Compatible setup

| Piece | Free Render |
|--------|-------------|
| Web service | Yes (Docker) |
| Postgres | **No** (use SQLite) |
| Redis | **No** (in-memory cache) |
| Persistent disk | **No** |
| FFmpeg | Yes (in image) |
| YouTube | Only with **durable cookies** in env |

## Deploy

1. Blueprint or existing `videodl-web` → deploy `main`
2. Login: `admin` / `ChangeMeNow123!`
3. For YouTube: run on your PC:

```powershell
.\scripts\set_render_cookies.ps1
```

4. Render → **videodl-web** → **Environment** → add:

| Key | Value |
|-----|--------|
| `YTDLP_COOKIES_BASE64` | paste from the script |

5. **Manual Deploy** (so the service restarts and loads cookies)

File uploads under Settings work until the free instance sleeps; **env base64 survives**.

## Free-tier limits (by design)

- Sleep after ~15 min idle → first request cold-starts
- SQLite + downloads wiped on sleep/redeploy
- Max **1** concurrent download, **512 MB** cap
- Heavy YouTube jobs can still hit memory limits

## Best platforms on free Render

Often OK without cookies: **TikTok, Instagram, X/Twitter, Vimeo, Reddit, SoundCloud**  
Needs cookies + still flaky: **YouTube**
