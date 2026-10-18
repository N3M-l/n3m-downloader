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
