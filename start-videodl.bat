@echo off
cd /d "%~dp0"
echo Starting VideoDL Pro on http://127.0.0.1:4000 ...
call .venv\Scripts\activate.bat
python manage.py migrate --noinput
daphne -b 0.0.0.0 -p 4000 config.asgi:application
pause
