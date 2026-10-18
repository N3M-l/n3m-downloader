FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    N3M_WORK_DIR=/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        ca-certificates \
        curl \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Optional free WARP egress for YouTube on flagged datacenter IPs.
RUN curl -fsSL -o /tmp/warp-plus.zip \
        https://github.com/bepass-org/warp-plus/releases/download/v1.2.6/warp-plus_linux-amd64.zip \
    && unzip -q /tmp/warp-plus.zip -d /tmp/warp \
    && install -m 0755 /tmp/warp/warp-plus /usr/local/bin/warp-plus \
    && rm -rf /tmp/warp-plus.zip /tmp/warp

# yt-dlp requires a JavaScript runtime to handle YouTube player scripts.
# Pin and checksum-verify the official Deno x86_64 Linux distribution.
ARG DENO_VERSION=2.9.7
ARG DENO_SHA256=c6527f24f4b16031d3ae4fa9f658d5f11534c8d84ce7dc8502420280919c3490
RUN curl --fail --location --silent --show-error --retry 3 \
        "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" \
        --output /tmp/deno.zip \
    && echo "${DENO_SHA256}  /tmp/deno.zip" | sha256sum --check - \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && rm -f /tmp/deno.zip \
    && /usr/local/bin/deno --version

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

RUN useradd --create-home --uid 10001 n3m \
    && mkdir -p /data \
    && chown -R n3m:n3m /app /data

USER n3m

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
