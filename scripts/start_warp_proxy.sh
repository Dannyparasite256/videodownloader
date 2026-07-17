#!/usr/bin/env bash
# Start Cloudflare WARP as a local SOCKS5 proxy for yt-dlp (bypasses datacenter IP blocks).
# Requires wgcf + wireproxy on PATH (installed in Docker image).
set -uo pipefail

WARP_DIR="${WARP_DIR:-/app/warp}"
SOCKS_ADDR="${WARP_SOCKS_ADDR:-127.0.0.1:1080}"
mkdir -p "$WARP_DIR"
cd "$WARP_DIR" || exit 1

if ! command -v wgcf >/dev/null 2>&1 || ! command -v wireproxy >/dev/null 2>&1; then
  echo "[warp] wgcf/wireproxy not installed — skip"
  exit 0
fi

# Register + generate WireGuard profile once (persists on disk if available)
if [[ ! -f wgcf-account.toml ]]; then
  echo "[warp] registering Cloudflare WARP account…"
  wgcf register --accept-tos 2>/dev/null || wgcf register --accept-tos
fi
if [[ ! -f wgcf-profile.conf ]]; then
  echo "[warp] generating WireGuard profile…"
  wgcf generate
fi

# Ensure SOCKS5 listener section exists
if ! grep -q '^\[Socks5\]' wgcf-profile.conf 2>/dev/null; then
  cat >> wgcf-profile.conf <<EOF

[Socks5]
BindAddress = ${SOCKS_ADDR}
EOF
fi

# Already running?
if curl -fsS --max-time 2 --socks5-hostname "${SOCKS_ADDR}" https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -q warp=; then
  echo "[warp] already up at socks5://${SOCKS_ADDR}"
  exit 0
fi

# Kill stale wireproxy
pkill -f "wireproxy.*wgcf-profile" 2>/dev/null || true
sleep 0.5

echo "[warp] starting wireproxy on ${SOCKS_ADDR}…"
nohup wireproxy -c "${WARP_DIR}/wgcf-profile.conf" >"${WARP_DIR}/wireproxy.log" 2>&1 &
echo $! >"${WARP_DIR}/wireproxy.pid"

# Wait until SOCKS accepts connections (up to ~25s)
for i in $(seq 1 25); do
  if curl -fsS --max-time 2 --socks5-hostname "${SOCKS_ADDR}" https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -q .; then
    echo "[warp] ready socks5://${SOCKS_ADDR}"
    # Prefer routing yt-dlp through WARP on cloud hosts
    export YTDLP_PROXY="socks5://${SOCKS_ADDR}"
    # Write env file for parent shell to source
    echo "export YTDLP_PROXY=socks5://${SOCKS_ADDR}" >"${WARP_DIR}/env.sh"
    exit 0
  fi
  sleep 1
done

echo "[warp] failed to become ready — check ${WARP_DIR}/wireproxy.log"
tail -n 30 "${WARP_DIR}/wireproxy.log" 2>/dev/null || true
exit 1
