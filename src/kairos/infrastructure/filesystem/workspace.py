"""Workspace discovery and bootstrap. All KAIROS writes are confined to ``.kairos/``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kairos.domain.errors import WorkspaceAlreadyExistsError, WorkspaceNotFoundError

KAIROS_DIR_NAME = ".kairos"
DB_FILENAME = "kairos.db"
EVENTS_FILENAME = "events.jsonl"
CONFIG_FILENAME = "config.json"
CONTENT_DIRNAME = "content"


@dataclass(frozen=True, slots=True)
class Workspace:
    """A resolved KAIROS workspace: a directory containing ``.kairos/``."""

    root: Path

    @property
    def kairos_dir(self) -> Path:
        return self.root / KAIROS_DIR_NAME

    @property
    def db_path(self) -> Path:
        return self.kairos_dir / DB_FILENAME

    @property
    def events_path(self) -> Path:
        return self.kairos_dir / EVENTS_FILENAME

    @property
    def config_path(self) -> Path:
        return self.kairos_dir / CONFIG_FILENAME

    @property
    def content_dir(self) -> Path:
        return self.kairos_dir / CONTENT_DIRNAME

    def relative_path(self, path: Path) -> str:
        """Render an absolute path as workspace-relative, for provenance display."""
        try:
            return str(path.resolve().relative_to(self.root.resolve()).as_posix())
        except ValueError:
            return str(path.resolve().as_posix())


def find_workspace(start: Path) -> Workspace:
    """Walk upward from ``start`` looking for a directory containing ``.kairos/``."""
    current = start.resolve()
    while True:
        if (current / KAIROS_DIR_NAME).is_dir():
            return Workspace(root=current)
        if current.parent == current:
            raise WorkspaceNotFoundError(
                f"No {KAIROS_DIR_NAME}/ found in {start} or any parent directory. "
                "Run `kairos init <workspace>` first."
            )
        current = current.parent


def init_workspace(root: Path, *, name: str | None = None) -> Workspace:
    """Create a new workspace at ``root``. Fails if ``.kairos/`` already exists."""
    root = root.resolve()
    kairos_dir = root / KAIROS_DIR_NAME
    if kairos_dir.exists():
        raise WorkspaceAlreadyExistsError(f"{kairos_dir} already exists.")

    root.mkdir(parents=True, exist_ok=True)
    kairos_dir.mkdir(parents=True)
    (kairos_dir / CONTENT_DIRNAME).mkdir()

    config = {
        "name": name or root.name,
        "created_at": datetime.now(UTC).isoformat(),
        "schema_version": "0001",
    }
    (kairos_dir / CONFIG_FILENAME).write_text(json.dumps(config, indent=2), encoding="utf-8")
    (kairos_dir / EVENTS_FILENAME).touch()

    return Workspace(root=root)
