"""Content-addressed raw source storage. Raw bytes are never overwritten or mutated."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoredContent:
    sha256: str
    size_bytes: int
    stored_path: Path


class ContentStore:
    """Stores a copy of every ingested file's raw bytes, addressed by sha256.

    If the same bytes are ingested again, the existing stored copy is left
    untouched (write-once) and its hash is returned — ``ingest`` decides
    whether that's a no-op or a new artifact record pointing at the same
    content.
    """

    def __init__(self, content_dir: Path) -> None:
        self._content_dir = content_dir

    def _path_for(self, sha256: str) -> Path:
        return self._content_dir / sha256[:2] / sha256

    def put(self, source_path: Path) -> StoredContent:
        digest = hashlib.sha256()
        with source_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        sha256 = digest.hexdigest()
        size_bytes = source_path.stat().st_size

        dest = self._path_for(sha256)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, dest)
            dest.chmod(0o444)  # read-only: raw source is never mutated after ingest

        return StoredContent(sha256=sha256, size_bytes=size_bytes, stored_path=dest)

    def read_bytes(self, sha256: str) -> bytes:
        return self._path_for(sha256).read_bytes()

    def path_for(self, sha256: str) -> Path:
        return self._path_for(sha256)
