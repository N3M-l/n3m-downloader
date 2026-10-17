from __future__ import annotations

import os
import time
import zipfile

from app.storage import (
    cleanup_old_jobs,
    directory_size,
    disk_status,
    ensure_extension,
    pick_output,
    safe_filename,
    zip_directory,
)


def test_safe_filename_blocks_traversal():
    name = safe_filename("../../etc/passwd")
    assert "/" not in name
    assert "\\" not in name
    assert not name.startswith("..")


def test_safe_filename_windows_reserved():
    assert safe_filename("CON.mp4") == "_CON.mp4"
    assert safe_filename("lpt1") == "_lpt1"


def test_safe_filename_arabic_preserved():
    name = safe_filename("فيديو رائع.mp4")
    assert name == "فيديو رائع.mp4"


def test_ensure_extension():
    assert ensure_extension("clip", "mp4") == "clip.mp4"
    assert ensure_extension("clip.MP4", "mp4") == "clip.MP4"


def test_zip_directory(workdir):
    source = workdir / "album"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"a" * 10)
    (source / "b.jpg").write_bytes(b"b" * 20)
    archive = workdir / "album.zip"
    count, size = zip_directory(source, archive)
    assert count == 2
    assert size == 30
    with zipfile.ZipFile(archive) as zipped:
        assert set(zipped.namelist()) == {"a.jpg", "b.jpg"}


def test_pick_output_skips_partials(workdir):
    (workdir / "video.mp4").write_bytes(b"x" * 100)
    (workdir / "video.mp4.part").write_bytes(b"x" * 300)
    chosen = pick_output(workdir)
    assert chosen is not None
    assert chosen.name == "video.mp4"


def test_cleanup_old_jobs(workdir):
    old = workdir / "old"
    old.mkdir()
    (old / "file.bin").write_bytes(b"x" * 50)
    fresh = workdir / "fresh"
    fresh.mkdir()
    (fresh / "file.bin").write_bytes(b"x" * 5)
    past = time.time() - 3600
    os.utime(old, (past, past))
    result = cleanup_old_jobs(workdir, retention_minutes=10)
    assert result["removedJobs"] == 1
    assert result["freedBytes"] == 50
    assert not old.exists()
    assert fresh.exists()


def test_disk_status_shape(workdir):
    status = disk_status(workdir, 0)
    assert status["ok"] is True
    assert status["freeGb"] >= 0
    assert "totalGb" in status


def test_directory_size(workdir):
    (workdir / "a").write_bytes(b"a" * 3)
    (workdir / "b").write_bytes(b"b" * 7)
    assert directory_size(workdir) == 10
