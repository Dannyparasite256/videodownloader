# Best place to run VideoDL Pro (avoid YouTube bot blocks)

Cloud hosts (Render, Railway, AWS, etc.) use **datacenter IPs**.
YouTube often blocks those with “Sign in to confirm you’re not a bot”.

**Best setup for reliable YouTube access:** run on your **home PC**
(residential IP), same machine you use for browsing.

## Start the app (Windows)

Double-click:

```text
start-videodl.bat
```

Or in PowerShell:

```powershell
cd "C:\Users\TECNO\Desktop\django downloader"
.\.venv\Scripts\activate
daphne -b 0.0.0.0 -p 4000 config.asgi:application
```

Open: **http://127.0.0.1:4000**

### Default admin
- Username: `admin`
- Password: `admin12345admin`  
  (change this after first login)

## Optional: public URL from home (Cloudflare Tunnel)

Keeps traffic on your home IP (usually better for YouTube than Render):

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/)
2. Run:

```powershell
cloudflared tunnel --url http://127.0.0.1:4000
```

3. Use the `https://….trycloudflare.com` link Cloudflare prints.

For a permanent domain, create a named tunnel in the Cloudflare Zero Trust dashboard.

## If YouTube still blocks

Put Netscape `cookies.txt` in:

```text
secrets\cookies.txt
```

Or upload via **Settings → YouTube cookies** (logged in as admin).

## Why not Render for YouTube?

Render is fine for hosting the UI, but YouTube bot checks are common there.
This home deploy is the configuration that “works very well” for downloads.
