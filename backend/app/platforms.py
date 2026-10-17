"""Platform discovery for user-supplied links."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

DIRECT_FILE_EXTENSIONS = frozenset(
    {
        "mp4",
        "mkv",
        "webm",
        "mov",
        "avi",
        "flv",
        "mp3",
        "m4a",
        "wav",
        "flac",
        "ogg",
        "opus",
        "aac",
        "zip",
        "rar",
        "7z",
        "tar",
        "gz",
        "pdf",
        "doc",
        "docx",
        "apk",
        "exe",
        "dmg",
        "iso",
        "img",
        "jpg",
        "jpeg",
        "png",
        "gif",
        "webp",
        "avif",
        "svg",
        "bmp",
    }
)


@dataclass(frozen=True, slots=True)
class Platform:
    key: str
    label: str
    emoji: str
    kind: str  # video | audio | images | file | auto


PLATFORMS: dict[str, Platform] = {
    "youtube": Platform("youtube", "YouTube", "📺", "video"),
    "tiktok": Platform("tiktok", "TikTok", "🎵", "video"),
    "instagram": Platform("instagram", "Instagram", "📸", "video"),
    "x": Platform("x", "X / Twitter", "🐦", "video"),
    "soundcloud": Platform("soundcloud", "SoundCloud", "🎧", "audio"),
    "pinterest": Platform("pinterest", "Pinterest", "📌", "images"),
    "reddit": Platform("reddit", "Reddit", "👾", "video"),
    "vimeo": Platform("vimeo", "Vimeo", "🎬", "video"),
    "file": Platform("file", "ملف مباشر", "📁", "file"),
    "unknown": Platform("unknown", "رابط عام", "🌐", "auto"),
}

PLATFORM_HOSTS: tuple[tuple[str, str], ...] = (
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("youtube-nocookie.com", "youtube"),
    ("tiktok.com", "tiktok"),
    ("instagram.com", "instagram"),
    ("instagr.am", "instagram"),
    ("x.com", "x"),
    ("twitter.com", "x"),
    ("t.co", "x"),
    ("soundcloud.com", "soundcloud"),
    ("snd.sc", "soundcloud"),
    ("pinterest.com", "pinterest"),
    ("pinterest.co.uk", "pinterest"),
    ("pin.it", "pinterest"),
    ("reddit.com", "reddit"),
    ("redd.it", "reddit"),
    ("vimeo.com", "vimeo"),
)


def normalize_host(host: str) -> str:
    value = (host or "").strip().lower().rstrip(".")
    for prefix in ("www.", "m.", "mobile.", "music.", "open."):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return value


def host_matches(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith("." + suffix)


def url_extension(url: str) -> str:
    try:
        path = urlsplit(url).path
    except ValueError:
        return ""
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def looks_like_direct_file(url: str) -> bool:
    return url_extension(url) in DIRECT_FILE_EXTENSIONS


def detect_platform(url: str) -> Platform:
    try:
        host = normalize_host(urlsplit(url).hostname or "")
    except ValueError:
        return PLATFORMS["unknown"]
    for suffix, key in PLATFORM_HOSTS:
        if host_matches(host, suffix):
            return PLATFORMS[key]
    if looks_like_direct_file(url):
        return PLATFORMS["file"]
    return PLATFORMS["unknown"]


def suggested_mode(platform: Platform) -> str:
    if platform.key == "soundcloud":
        return "audio"
    if platform.key in {"pinterest"}:
        return "images"
    if platform.key == "file":
        return "file"
    return "video"
