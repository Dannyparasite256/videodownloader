#!/usr/bin/env bash
# Start Cloudflare WARP as a local SOCKS5 proxy for yt-dlp (bypasses datacenter IP blocks).
# Non-blocking: starts wireproxy and returns quickly so the web process can pass health checks.
set -uo pipefail

WARP_DIR="${WARP_DIR:-/app/warp}"
SOCKS_ADDR="${WARP_SOCKS_ADDR:-127.0.0.1:1080}"
mkdir -p "$WARP_DIR"
cd "$WARP_DIR" || exit 0

if ! command -v wgcf >/dev/null 2>&1 || ! command -v wireproxy >/dev/null 2>&1; then
  echo "[warp] wgcf/wireproxy not installed — skip"
  exit 0
fi

register_warp() {
  if [[ ! -f wgcf-account.toml ]]; then
    echo "[warp] registering Cloudflare WARP…"
    # wgcf may prompt; --accept-tos for non-interactive
    wgcf register --accept-tos >>"${WARP_DIR}/wgcf.log" 2>&1 || true
  fi
  if [[ ! -f wgcf-profile.conf ]]; then
    echo "[warp] generating profile…"
    wgcf generate >>"${WARP_DIR}/wgcf.log" 2>&1 || true
  fi
  if [[ -f wgcf-profile.conf ]] && ! grep -q '^\[Socks5\]' wgcf-profile.conf 2>/dev/null; then
    cat >> wgcf-profile.conf <<EOF

[Socks5]
BindAddress = ${SOCKS_ADDR}
EOF
  fi
}

register_warp

if [[ ! -f wgcf-profile.conf ]]; then
  echo "[warp] no profile — YouTube may stay blocked on this host"
  exit 0
fi

# Already running?
if curl -fsS --max-time 2 --socks5-hostname "${SOCKS_ADDR}" https://1.1.1.1 2>/dev/null | grep -q .; then
  echo "[warp] already up socks5://${SOCKS_ADDR}"
  echo "export YTDLP_PROXY=socks5://${SOCKS_ADDR}" >"${WARP_DIR}/env.sh"
  exit 0
fi

pkill -f "wireproxy.*wgcf-profile" 2>/dev/null || true
sleep 0.3

echo "[warp] starting wireproxy…"
nohup wireproxy -c "${WARP_DIR}/wgcf-profile.conf" >"${WARP_DIR}/wireproxy.log" 2>&1 &
echo $! >"${WARP_DIR}/wireproxy.pid"

# Brief wait only (do not block Render health for long)
for i in 1 2 3 4 5 6 7 8; do
  if curl -fsS --max-time 2 --socks5-hostname "${SOCKS_ADDR}" https://1.1.1.1 >/dev/null 2>&1; then
    echo "[warp] ready socks5://${SOCKS_ADDR}"
    echo "export YTDLP_PROXY=socks5://${SOCKS_ADDR}" >"${WARP_DIR}/env.sh"
    exit 0
  fi
  sleep 1
done

# Still export proxy path; yt-dlp may connect once wireproxy finishes handshake
echo "export YTDLP_PROXY=socks5://${SOCKS_ADDR}" >"${WARP_DIR}/env.sh"
echo "[warp] started (warming); proxy socks5://${SOCKS_ADDR}"
exit 0
