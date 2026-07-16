@echo off
cd /d "%~dp0"
echo.
echo === VideoDL: prepare YouTube cookies for Render ===
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\set_render_cookies.ps1"
echo.
echo NEXT (required once):
echo  1. Render Dashboard is open or go to https://dashboard.render.com
echo  2. Click videodl-web -^> Environment
echo  3. Add Variable:
echo       Key:   YTDLP_COOKIES_BASE64
echo       Value: Ctrl+V  (already on clipboard)
echo  4. Save -^> Manual Deploy -^> Deploy latest commit
echo  5. Wait Live, then open https://videodl-web.onrender.com
echo.
echo Login: admin / ChangeMeNow123!
echo.
pause
