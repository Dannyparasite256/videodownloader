# VideoDL Pro — helper to open the right pages for cookie export
$Root = Split-Path -Parent $PSScriptRoot
$Secrets = Join-Path $Root "secrets"
New-Item -ItemType Directory -Force -Path $Secrets | Out-Null

Write-Host ""
Write-Host "=== YouTube cookies setup ===" -ForegroundColor Cyan
Write-Host "1) Log into YouTube in Chrome/Edge if you are not already."
Write-Host "2) Install extension: Get cookies.txt LOCALLY"
Write-Host "3) On youtube.com click the extension -> Export"
Write-Host "4) Save the file as:"
Write-Host "   $Secrets\cookies.txt" -ForegroundColor Yellow
Write-Host "5) Come back here and press Enter after the file is saved."
Write-Host ""

Start-Process "https://www.youtube.com"
Start-Process "https://chromewebstore.google.com/search/get%20cookies.txt%20LOCALLY"
Start-Process explorer.exe $Secrets

$null = Read-Host "Press Enter after you saved secrets\cookies.txt"

$cookie = Join-Path $Secrets "cookies.txt"
if (-not (Test-Path $cookie)) {
  Write-Host "ERROR: $cookie not found." -ForegroundColor Red
  exit 1
}
$size = (Get-Item $cookie).Length
if ($size -lt 50) {
  Write-Host "ERROR: cookies.txt looks empty ($size bytes)." -ForegroundColor Red
  exit 1
}
$text = Get-Content $cookie -Raw
if ($text -notmatch "youtube") {
  Write-Host "WARNING: file may not contain youtube cookies. Export again from youtube.com" -ForegroundColor Yellow
}

Write-Host "OK: cookies.txt found ($size bytes). Testing yt-dlp..." -ForegroundColor Green
Set-Location $Root
& .\.venv\Scripts\python.exe manage.py check_ytdlp "https://www.youtube.com/watch?v=jNQXAC9IVRw"
if ($LASTEXITCODE -eq 0) {
  Write-Host ""
  Write-Host "Success! Restart the app if it was already running, then try Analyze in the UI." -ForegroundColor Green
} else {
  Write-Host ""
  Write-Host "Still failing. Export a FRESH cookies.txt while logged into YouTube and run this script again." -ForegroundColor Red
}
