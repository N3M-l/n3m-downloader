"""One real, authorized public MP4 download through N3M staging API.

No cookies, no credentials, no private addresses, and a 12MB response cap.
The sample is provided as a public test file by samplelib.com.
"""
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin

BASE = "https://n3m-downloader-engine-us.onrender.com"
SAMPLE = "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
HEADERS = {"Origin": "https://n3m.fun", "User-Agent": "N3M-Staging-Diagnostic/1.0"}
CAP = 12 * 1024 * 1024

def request(method, path, body=None, timeout=35):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(urljoin(BASE, path), data=data, headers=headers, method=method)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as err:
        detail = err.read(500)
        raise RuntimeError(f"{method} returned HTTP {err.code}: {detail[:250]!r}") from None

def main():
    with request("GET", "/health") as r:
        print("STAGING_HEALTH", r.status)
        if r.status != 200:
            raise RuntimeError("Staging API health check failed")
    with request("POST", "/api/download", {"url": SAMPLE, "mode": "file"}) as r:
        job = json.load(r)
        print("DIRECT_JOB_STARTED", r.status, bool(job.get("jobId")))
    jid = job["jobId"]
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        time.sleep(3)
        with request("GET", f"/api/jobs/{jid}") as r:
            status = json.load(r)
        if status["status"] in ("completed", "failed", "cancelled", "expired"):
            break
    else:
        raise RuntimeError("Direct MP4 download timed out")
    print("DIRECT_JOB_STATUS", status["status"])
    if status["status"] != "completed":
        print("DIRECT_JOB_ERROR", str(status.get("message") or status.get("error"))[:200])
        raise RuntimeError("Direct MP4 staging download failed")
    target = status.get("downloadPath")
    if not target:
        raise RuntimeError("Completed job missing downloadPath")
    with request("GET", target, timeout=65) as r:
        data = r.read(CAP + 1)
        ctype = r.headers.get("Content-Type", "")
    if len(data) > CAP:
        raise RuntimeError("Direct MP4 response exceeded safety cap")
    valid_mp4 = b"ftyp" in data[:32]
    print("DIRECT_FILE_VERIFIED", r.status, "bytes", len(data), "mp4_header", valid_mp4, "type", ctype[:64])
    if len(data) < 4096 or not valid_mp4:
        raise RuntimeError("Downloaded file did not contain a valid MP4 header")
    print("DIRECT_DOWNLOAD_TEST_SUCCESS")

if __name__ == "__main__":
    main()
