"""Controlled end-to-end YouTube smoke test for the staging N3M engine.

Uses an existing short clip confirmed to be CC BY on Wikimedia Commons:
https://commons.wikimedia.org/wiki/File:That's_ONE_way_to_pass_a_driving_test_-_Romeo_-shorts.webm
This is a development-only test; never requires, prints or uploads cookies.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("N3M_SMOKE_ENGINE", "https://n3m-downloader-engine-us.onrender.com").rstrip("/")
VIDEO = "https://www.youtube.com/watch?v=Zl-HU2U85lI"
HEADERS = {"Origin": "https://n3m.fun", "User-Agent": "N3M-Smoke-Test/1.0"}

def req(method, path, payload=None, timeout=35):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as err:
        return err.code, err.read(), err.headers

def report(label, status, body):
    try:
        content = json.loads(body)
    except (ValueError, TypeError):
        content = {"detail": body[:400].decode("utf-8", "replace") if isinstance(body, bytes) else str(body)[:400]}
    detail = content.get("error") or content.get("detail") or content.get("message") or "OK"
    print(label, "HTTP", status, str(detail)[:350], flush=True)

def run():
    status, body, _ = req("GET", "/health", timeout=30)
    report("health", status, body)
    if status != 200:
        return 1

    status, body, _ = req("POST", "/api/inspect", {"url": VIDEO}, timeout=105)
    report("inspect", status, body)
    if status != 200:
        # Inspection failure is useful evidence, but also check whether actual download fails.
        pass

    status, body, _ = req("POST", "/api/download", {"url": VIDEO, "mode": "video", "quality": "360"}, timeout=40)
    report("download-start", status, body)
    if status != 202:
        return 1
    job_id = json.loads(body)["jobId"]
    deadline = time.monotonic() + 140
    while time.monotonic() < deadline:
        time.sleep(3)
        status, response, _ = req("GET", "/api/jobs/" + job_id, timeout=25)
        if status != 200:
            report("job-poll", status, response)
            return 1
        obj = json.loads(response)
        if obj.get("status") not in ("completed", "failed", "expired", "cancelled"):
            continue
        print("job result", obj.get("status"), "message", str(obj.get("message"))[:250], "size", obj.get("downloadedBytes"), flush=True)
        if obj.get("status") != "completed":
            return 1
        download_path = obj.get("downloadPath")
        if not download_path:
            print("no downloadPath", flush=True)
            return 1
        # Stream the actual file into a capped buffer, not merely HTTP headers.
        status, media, headers = req("GET", download_path, timeout=65)
        fmt = media[:32]
        playable_signature = b"ftyp" in fmt or fmt.startswith(b"\x1a\x45\xdf\xa3") or fmt.startswith(b"RIFF")
        print("file", status, "bytes", len(media), "media-type", headers.get("Content-Type"), "valid-header", playable_signature, flush=True)
        return 0 if status == 200 and len(media) > 4096 and playable_signature else 1
    print("timeout waiting for completed job", flush=True)
    return 1

if __name__ == "__main__":
    sys.exit(run())
