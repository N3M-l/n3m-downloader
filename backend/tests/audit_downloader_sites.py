"""Read-only public-site network analysis and one permitted media request.

Uses mitmproxy as a local HTTP(S) inspection proxy and Playwright to drive
normal browser UI. No CAPTCHA handling, no private API replay, no cookies,
no credentials, no requests to hidden endpoints, no stored HAR files.
Only tests public links and authorized media, limits each site to one attempt.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

SITES = (
    ("N3M Downloader", "https://n3m.fun/downloader/", True),
    ("Cobalt", "https://cobalt.tools/", True),
    ("Snapinsta (page only)", "https://snapinsta.app/", False),
)
# Comparison clip previously used for authorized testing in project.
MEDIA_URL = "https://www.youtube.com/watch?v=Zl-HU2U85lI"

async def check_site(browser, name: str, url: str, attempt: bool):
    context = await browser.new_context(ignore_https_errors=True, accept_downloads=True)
    page = await context.new_page()
    host_counts = Counter()
    def on_response(response):
        try:
            host = urlsplit(response.url).hostname or ""
            if host:
                host_counts[(host, response.status)] += 1
        except Exception:
            pass
    page.on("response", on_response)
    downloads = []
    page.on("download", lambda d: downloads.append(d))
    print(f"TEST_SITE {name}: {url}", flush=True)
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await page.wait_for_timeout(3500)
        title = (await page.title())[:100]
        inputs = await page.locator('input:not([type="hidden"]), textarea').count()
        buttons = await page.locator("button").count()
        print(f"PAGE status={response.status if response else 'unknown'} title={title!r} inputs={inputs} buttons={buttons}", flush=True)
        print("NETWORK top_hosts=" + repr(host_counts.most_common(10)), flush=True)
        if not attempt:
            print("ACTION page-only (no third-party submission)", flush=True)
            return
        # Only perform an ordinary UI submit using the public test-video URL.
        candidates = page.locator('input[type="url"], input[type="text"], textarea, input:not([type])')
        filled = False
        for i in range(min(8, await candidates.count())):
            item = candidates.nth(i)
            if await item.is_visible():
                await item.fill(MEDIA_URL, timeout=4000)
                filled = True
                break
        if not filled:
            print("ACTION unable-to-find-visible-link-input; skipped", flush=True)
            return
        button = page.get_by_role("button", name=re.compile(r"(download|تحميل|save|get)", re.I))
        if await button.count() == 0:
            print("ACTION unable-to-find-named-download-button; skipped", flush=True)
            return
        await button.first.click(timeout=10000)
        await page.wait_for_timeout(27000)
        print("ACTION submitted-one-public-test-link", flush=True)
        if downloads:
            try:
                d = downloads[0]
                path = await d.path()
                if path:
                    with open(path, "rb") as f:
                        header = f.read(32)
                    size = Path(path).stat().st_size
                    signature = b"ftyp" in header or header.startswith(bytes.fromhex("1a45dfa3"))
                    print(f"FILE received=true bytes={size} is_media={signature}", flush=True)
                else:
                    print("FILE started-but-no-path", flush=True)
            except Exception as exc:
                print("FILE error=" + type(exc).__name__, flush=True)
        else:
            body = (await page.locator("body").inner_text(timeout=5000))[-1500:]
            failed = any(s in body.lower() for s in ("bot", "failed", "error", "تعذر", "تحقق"))
            print(f"FILE no-browser-download error_or_challenge_on_page={failed}", flush=True)
        print("NETWORK final_top_hosts=" + repr(host_counts.most_common(12)), flush=True)
    except Exception as exc:
        print(f"TEST_ERROR type={type(exc).__name__} description={str(exc)[:300]}", flush=True)
    finally:
        await context.close()

async def main():
    with tempfile.TemporaryDirectory() as tdir:
        log = Path(tdir) / "mitm.log"
        cmd = [
            "mitmdump", "--listen-host", "127.0.0.1",
            "--listen-port", "18769", "--set", "ssl_insecure=true",
            "--quiet", "--scripts", "backend/tests/mitm_public_site_audit.py",
        ]
        with log.open("w") as dest:
            proc = subprocess.Popen(cmd, stdout=dest, stderr=subprocess.STDOUT)
            try:
                await asyncio.sleep(3)
                if proc.poll() is not None:
                    print("PROXY_FAILED startup", flush=True)
                    return
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True, proxy={"server": "http://127.0.0.1:18769"},
                    )
                    for name, url, attempt in SITES:
                        await check_site(browser, name, url, attempt)
                    await browser.close()
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        # Only the scrubbed proxy summary; never publish a raw traffic capture.
        text = log.read_text(errors="replace")
        start = text.find("SAFE_MITMPROXY_SUMMARY_BEGIN")
        stop = text.find("SAFE_MITMPROXY_SUMMARY_END")
        if start >= 0 and stop > start:
            print(text[start:stop + len("SAFE_MITMPROXY_SUMMARY_END")], flush=True)
        else:
            print("PROXY_SUMMARY unavailable; proxy exit=" + str(proc.returncode), flush=True)

if __name__ == "__main__":
    asyncio.run(main())
