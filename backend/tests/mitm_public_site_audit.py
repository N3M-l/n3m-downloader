"""Minimal mitmproxy addon: aggregate public response counts only.

Never log cookies, headers, query strings, response bodies, tokens, or full URLs.
"""
from collections import Counter
from mitmproxy import http

counts = Counter()

def response(flow: http.HTTPFlow) -> None:
    host = flow.request.pretty_host.lower()
    if not any(host == h or host.endswith("." + h) for h in (
        "n3m.fun", "cobalt.tools", "snapinsta.app",
    )):
        return
    counts[(host, flow.request.method, flow.response.status_code)] += 1

def done() -> None:
    print("SAFE_MITMPROXY_SUMMARY_BEGIN", flush=True)
    for (host, method, status), number in counts.most_common(30):
        print(f"{host} {method} HTTP {status} count={number}", flush=True)
    print("SAFE_MITMPROXY_SUMMARY_END", flush=True)
