#!/bin/sh
set -e

# Optional Cloudflare WARP egress for YouTube (free, userspace, no account).
if [ "${WARP_ENABLED:-0}" = "1" ]; then
    mkdir -p /data/warp
    /usr/local/bin/warp-plus \
        --bind 127.0.0.1:8086 \
        --cache-dir /data/warp \
        -4 &
    sleep 12
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers
