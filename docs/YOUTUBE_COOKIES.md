# YouTube “Sign in to confirm you’re not a bot”

YouTube often blocks **server / datacenter IPs** (including Render) unless yt-dlp
sends a valid **logged-in browser cookie jar**. This is normal and documented by
[yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).

This app only uses cookies for extraction/download of URLs **you** provide.
Use your own account cookies, keep them secret, and only download content you
are allowed to access.

---

## Option A — Local development (easiest)

If Chrome/Edge/Firefox is installed on the machine running the app:

```env
YTDLP_COOKIES_FROM_BROWSER=chrome
# or: edge | firefox | brave | chromium
# optional profile: chrome:Default
```

Restart the app, try the YouTube URL again.

---

## Option B — cookies.txt file (recommended for Render / Docker)

### 1. Export cookies on your PC

1. Install a browser extension that exports **Netscape format** cookies, e.g.
   - Chrome/Edge: “Get cookies.txt LOCALLY” (or similar trusted tool)
2. Log into **YouTube** in that browser (normal account)
3. Open youtube.com → export cookies → save as `cookies.txt`

Official tips:  
https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies

### 2. Put the file on the server

**Docker / VPS**

```env
YTDLP_COOKIES_FILE=/app/secrets/cookies.txt
```

Mount or copy the file (never commit it to Git):

```bash
# example
mkdir -p secrets
# copy cookies.txt into secrets/
chmod 600 secrets/cookies.txt
```

**Render**

1. Encode the file (on your PC):

```bash
# PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt"))
```

```bash
# macOS / Linux
base64 -w0 cookies.txt
```

2. In Render → **videodl-web** → **Environment**:

| Key | Value |
|-----|--------|
| `YTDLP_COOKIES_BASE64` | paste the long base64 string |
| *(or)* `YTDLP_COOKIES_FILE` | path if you mount a secret file |

3. **Manual Deploy** → redeploy the web service.

The app writes base64 cookies to a temp file at startup and passes them to yt-dlp.

---

## Verify

```bash
# on server / Render shell
python -c "from django.conf import settings; print(settings.YTDLP_COOKIES_FILE)"
```

Then Analyze a YouTube URL again in the UI.

---

## Security

- **Never commit** `cookies.txt` or paste cookies into public chats  
- Treat cookies like a **password** (session hijack risk)  
- Rotate: log out other sessions / export fresh cookies if leaks are suspected  
- Add `secrets/` and `cookies.txt` to `.gitignore` (already recommended)

---

## Still failing?

1. Export **fresh** cookies after a normal browser login to YouTube  
2. Upgrade yt-dlp: `pip install -U yt-dlp` (image rebuild on Render)  
3. Try another public video ID  
4. Some videos are age/region restricted even with cookies  
