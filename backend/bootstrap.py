"""One-command local bootstrap: secrets, folders, engine report, next steps."""

from __future__ import annotations

import importlib.util
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
TRUSTED = "https://n3m.fun,https://www.n3m.fun,http://localhost:3000,http://127.0.0.1:3000"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def ensure_env() -> dict[str, str]:
    if ENV_FILE.exists():
        values = read_env()
        if values.get("ADMIN_TOKEN") and values.get("TICKET_SECRET"):
            print(f"ملف الإعدادات موجود: {ENV_FILE}")
            return values
        print("ملف .env موجود لكنه ينقصه رمز أو سر؛ سيُكمَل تلقائيًا.")
    else:
        print("إنشاء ملف إعدادات محلي جديد…")

    values = read_env()
    values.setdefault("N3M_ENV", "development")
    values.setdefault("ADMIN_TOKEN", secrets.token_urlsafe(24))
    values.setdefault("TICKET_SECRET", secrets.token_urlsafe(32))
    values.setdefault("TRUSTED_ORIGINS", TRUSTED)
    values.setdefault("MIN_FREE_GB", "2")
    values.setdefault("MAX_FILESIZE_MB", "2048")
    ENV_FILE.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
    print(f"تم حفظ الإعدادات في: {ENV_FILE}")
    return values


def module_ok(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def report(values: dict[str, str]) -> None:
    print("\n— حالة المحركات —")
    print(f"yt-dlp      : {'مثبّت' if module_ok('yt_dlp') else 'غير مثبّت (pip install yt-dlp)'}")
    print(
        f"gallery-dl  : {'مثبّت' if module_ok('gallery_dl') else 'غير مثبّت (pip install gallery-dl)'}"
    )
    ffmpeg = shutil.which(values.get("FFMPEG_BIN") or "ffmpeg")
    aria2c = shutil.which(values.get("ARIA2C_BIN") or "aria2c")
    print(f"FFmpeg      : {ffmpeg or 'غير مثبّت — winget install Gyan.FFmpeg'}")
    print(f"aria2c      : {aria2c or 'غير مثبّت — winget install aria2.aria2 (اختياري للتسريع)'}")

    token = values.get("ADMIN_TOKEN", "")
    print("\n— روابط التشغيل —")
    print("المحرك     : http://127.0.0.1:8765/health")
    print("الأداة     : http://localhost:3000 (بعد تشغيل الواجهة)")
    print("لوحة الإدارة: http://localhost:3000/admin/")
    print(f"\nرمز الإدارة (ADMIN_TOKEN): {token}")


def main() -> int:
    values = ensure_env()
    report(values)
    print("\nشغّل المحرك بالأمر:")
    print("  .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765")
    return 0


if __name__ == "__main__":
    sys.exit(main())
