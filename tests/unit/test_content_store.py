"""Content-addressed storage: hash addressing, no-overwrite, read-back."""

from __future__ import annotations

from pathlib import Path

from kairos.infrastructure.filesystem.content_store import ContentStore


def test_put_stores_by_sha256(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    source = tmp_path / "source.txt"
    source.write_text("hello kairos", encoding="utf-8")

    store = ContentStore(content_dir)
    stored = store.put(source)

    assert stored.size_bytes == len("hello kairos")
    assert store.read_bytes(stored.sha256) == b"hello kairos"
    assert store.path_for(stored.sha256).is_file()


def test_put_is_idempotent_and_never_overwrites(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    source = tmp_path / "source.txt"
    source.write_text("hello kairos", encoding="utf-8")

    store = ContentStore(content_dir)
    first = store.put(source)
    stored_path = store.path_for(first.sha256)
    original_mtime = stored_path.stat().st_mtime_ns

    second = store.put(source)

    assert second.sha256 == first.sha256
    assert stored_path.stat().st_mtime_ns == original_mtime


def test_different_content_gets_different_hash(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("aaa", encoding="utf-8")
    b.write_text("bbb", encoding="utf-8")

    store = ContentStore(content_dir)
    stored_a = store.put(a)
    stored_b = store.put(b)

    assert stored_a.sha256 != stored_b.sha256
