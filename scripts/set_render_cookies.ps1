# Print base64 of your YouTube cookies for Render Environment.
# 1) Export cookies to Downloads\www.youtube.com_cookies.txt (or secrets\cookies.txt)
# 2) Run this script
# 3) Render Dashboard → videodl-web → Environment → Add:
#      Key:   YTDLP_COOKIES_BASE64
#      Value: (paste the long string this script prints)
# 4) Manual Deploy → Deploy latest commit

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$candidates = @(
    (Join-Path $Root "secrets\cookies.txt"),
    (Join-Path $env:USERPROFILE "Downloads\www.youtube.com_cookies.txt"),
    (Join-Path $env:USERPROFILE "Downloads\cookies.txt"),
    (Join-Path $env:USERPROFILE "Desktop\cookies.txt")
)
$src = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $src) {
    Write-Host "No cookies.txt found. Export from Chrome (Get cookies.txt LOCALLY) first." -ForegroundColor Red
    exit 1
}
$bytes = [IO.File]::ReadAllBytes($src)
$b64 = [Convert]::ToBase64String($bytes)
Write-Host ""
Write-Host "Source: $src ($($bytes.Length) bytes)" -ForegroundColor Cyan
Write-Host "Copy EVERYTHING between the lines into Render env YTDLP_COOKIES_BASE64:" -ForegroundColor Yellow
Write-Host "---------- BEGIN ----------"
Write-Host $b64
Write-Host "---------- END ----------"
Write-Host ""
Write-Host "Also saved to secrets\cookies.b64.txt" -ForegroundColor Green
$out = Join-Path $Root "secrets\cookies.b64.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null
[IO.File]::WriteAllText($out, $b64)
try {
    Set-Clipboard -Value $b64
    Write-Host "Copied to clipboard." -ForegroundColor Green
} catch {
    Write-Host "Clipboard copy failed — select/copy the string manually." -ForegroundColor Yellow
}
