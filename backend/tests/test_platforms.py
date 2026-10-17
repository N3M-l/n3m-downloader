from __future__ import annotations

import asyncio

from app.platforms import detect_platform, looks_like_direct_file, suggested_mode
from app.rate_limit import SlidingWindowLimiter


def test_rate_limit_allows_then_denies():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)

    async def scenario():
        first = await limiter.check("1.2.3.4")
        second = await limiter.check("1.2.3.4")
        third = await limiter.check("1.2.3.4")
        other = await limiter.check("5.6.7.8")
        return first, second, third, other

    first, second, third, other = asyncio.run(scenario())
    assert first[0] is True
    assert second[0] is True
    assert third[0] is False
    assert third[1] >= 1
    assert other[0] is True


def test_platform_detection():
    cases = {
        "https://www.youtube.com/watch?v=abc": "youtube",
        "https://youtu.be/abc": "youtube",
        "https://vm.tiktok.com/abc": "tiktok",
        "https://www.instagram.com/reel/abc": "instagram",
        "https://x.com/user/status/1": "x",
        "https://twitter.com/user/status/1": "x",
        "https://soundcloud.com/artist/track": "soundcloud",
        "https://www.pinterest.com/pin/1": "pinterest",
        "https://www.reddit.com/r/test/comments/1": "reddit",
        "https://vimeo.com/123": "vimeo",
        "https://cdn.example.com/file.zip": "file",
        "https://example.com/page": "unknown",
    }
    for url, expected in cases.items():
        assert detect_platform(url).key == expected, url


def test_direct_file_extensions():
    assert looks_like_direct_file("https://example.com/a.mp4?token=1")
    assert looks_like_direct_file("https://example.com/a.ZIP")
    assert not looks_like_direct_file("https://example.com/watch")


def test_suggested_modes():
    assert suggested_mode(detect_platform("https://soundcloud.com/a/b")) == "audio"
    assert suggested_mode(detect_platform("https://pinterest.com/pin/1")) == "images"
    assert suggested_mode(detect_platform("https://example.com/a.zip")) == "file"
    assert suggested_mode(detect_platform("https://youtube.com/watch?v=1")) == "video"
