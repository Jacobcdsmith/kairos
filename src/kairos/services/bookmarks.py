"""TUI bookmarks — named, saved commands for quick recall via ``:bookmark``.

Stored as a single JSON array at ``.kairos/.bookmarks.json``, unlike command
history's append-only JSONL: bookmarks are a small, named, mutable set (save
overwrites, remove deletes), not an ever-growing log, so a whole-file
read/write is the simpler and correct model. Saving/removing a bookmark is a
deliberate user action, so — unlike command history, which fails closed —
I/O errors here are raised as ``KairosError`` so the user actually finds out
their bookmark didn't save.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kairos.domain.errors import BookmarkNotFoundError, KairosError
from kairos.schemas.bookmark import BookmarkResult
from kairos.services.context import RuntimeContext

BOOKMARKS_FILENAME = ".bookmarks.json"


def bookmarks_file_path(workspace_root: Path) -> Path:
    return workspace_root / ".kairos" / BOOKMARKS_FILENAME


def list_bookmarks(ctx: RuntimeContext) -> list[BookmarkResult]:
    """Oldest-saved first — mirrors command_history's ordering convention.
    Callers that want "most recent" (e.g. the tab bar) take from the end.
    """
    path = bookmarks_file_path(ctx.workspace.root)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KairosError(f"Could not read bookmarks: {exc}") from exc
    return [
        BookmarkResult(name=b["name"], command=b["command"], created_at=b["created_at"])
        for b in raw
    ]


def _write_bookmarks(workspace_root: Path, bookmarks: list[BookmarkResult]) -> None:
    path = bookmarks_file_path(workspace_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [b.model_dump(mode="json") for b in bookmarks]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise KairosError(f"Could not save bookmarks: {exc}") from exc


def save_bookmark(ctx: RuntimeContext, name: str, command: str) -> BookmarkResult:
    """Save (or overwrite) a bookmark. Re-saving an existing name moves it to
    the end of the list, so it counts as the most recent for the tab bar.
    """
    bookmarks = [b for b in list_bookmarks(ctx) if b.name != name]
    new_bookmark = BookmarkResult(name=name, command=command, created_at=datetime.now(UTC))
    bookmarks.append(new_bookmark)
    _write_bookmarks(ctx.workspace.root, bookmarks)
    return new_bookmark


def remove_bookmark(ctx: RuntimeContext, name: str) -> None:
    bookmarks = list_bookmarks(ctx)
    remaining = [b for b in bookmarks if b.name != name]
    if len(remaining) == len(bookmarks):
        raise BookmarkNotFoundError(f"No bookmark named {name!r}.")
    _write_bookmarks(ctx.workspace.root, remaining)
