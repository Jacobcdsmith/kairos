"""The TUI's explicit command grammar: ``:name arg1 arg2...``. Not a
natural-language parser — unknown input is a parse error, not a best-effort
guess.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_ALIASES: dict[str, str] = {
    "s": "search",
    "t": "trace",
    "q": "quit",
}

_KNOWN_COMMANDS = frozenset(
    {
        "home",
        "artifacts",
        "search",
        "show",
        "trace",
        "well",
        "config",
        "logs",
        "doctor",
        "history",
        "help",
        "refresh",
        "quit",
        "note",
        "ingest",
        "tutorial",
    }
)

# Commands whose last argument is free text and must not be word-split.
_FREEFORM_TAIL = {
    ("search",): 1,
    ("logs",): 1,
    ("note", "add"): 2,
}


class CommandParseError(Exception):
    """Raised for unrecognized commands or malformed argument counts.
    Always caught by the controller and turned into a status-line message —
    never allowed to propagate as a traceback.
    """


@dataclass(frozen=True, slots=True)
class Command:
    name: str
    args: tuple[str, ...]
    raw: str


def parse(text: str) -> Command:
    """Parse one command line. Accepts a leading ``:``, a bare ``?`` (alias
    for ``:help``), or nothing special otherwise (the caller is expected to
    only hand this function text that was entered as a command, not raw
    search text — the command line widget handles the ``/`` shorthand by
    prefilling ``:search `` before the user finishes typing).
    """
    raw = text
    stripped = text.strip()
    if stripped == "?":
        return Command(name="help", args=(), raw=raw)
    if not stripped.startswith(":"):
        raise CommandParseError(f"Not a command: {text!r}. Commands start with ':' — try :help.")

    body = stripped[1:].strip()
    if not body:
        raise CommandParseError("Empty command. Try :help.")

    parts = body.split()
    name = _ALIASES.get(parts[0], parts[0])

    if name not in _KNOWN_COMMANDS:
        suggestion = _closest(name)
        hint = f" Did you mean :{suggestion}?" if suggestion else ""
        raise CommandParseError(f"Unknown command: :{name}.{hint} Try :help.")

    rest = parts[1:]
    sub_key = (name, rest[0]) if name == "note" and rest else (name,)
    freeform_at = _FREEFORM_TAIL.get(sub_key)
    if freeform_at is not None and len(rest) > freeform_at:
        # Everything after the fixed-position args is one free-text argument
        # (a search query, a note body), collapsed to single spaces.
        rest = [*rest[:freeform_at], " ".join(rest[freeform_at:])]

    return Command(name=name, args=tuple(rest), raw=raw)


def _closest(name: str) -> str | None:
    for known in _KNOWN_COMMANDS:
        if known.startswith(name) or name.startswith(known):
            return known
    return None


# ── Command-line hints & autocomplete ─────────────────────────────────────
# Names exported for the command line widget's `Suggester` (ghost-text
# completion) — kept as the same frozenset the parser validates against so
# the two never drift.
KNOWN_COMMAND_NAMES = _KNOWN_COMMANDS

_COMMAND_HINTS: dict[str, str] = {
    "home": "dashboard of workspace stats and recent activity",
    "artifacts": "list ingested artifacts, optionally filtered by kind",
    "search": "full-text search over ingested content",
    "show": "show one artifact's structured detail and spans",
    "trace": "trace an entity or term through its typed relations",
    "well": "list/use/clear/show coherence wells (scoped views)",
    "config": "show a Kconfig symbol's definition and provenance",
    "logs": "search parsed log lines",
    "doctor": "run workspace health checks (read-only)",
    "history": "this session's command history (--clear to wipe it)",
    "help": "open the help overlay",
    "note": "add or list notes on an artifact/span",
    "ingest": "ingest a file or directory into the workspace",
    "tutorial": "open the guided tutorial overlay",
    "refresh": "re-run the last successful command",
    "quit": "quit the TUI",
}


def hint_text(partial: str) -> str:
    """One-line hint for whatever command name is currently being typed at
    the command line, shown just below it. Returns ``""`` when there's
    nothing useful to show — not yet typing a command, or the input is
    still just ``:`` — since an unrecognized command is already covered by
    the parser's own error message once submitted.
    """
    stripped = partial.strip()
    if not stripped.startswith(":"):
        return ""
    body = stripped[1:]
    typed_name = body.split()[0] if body else ""
    if not typed_name:
        return ""
    name = _ALIASES.get(typed_name, typed_name)
    if name in _KNOWN_COMMANDS:
        return f":{name} — {_COMMAND_HINTS.get(name, '')}"
    matches = sorted(n for n in _KNOWN_COMMANDS if n.startswith(name))
    if not matches:
        return ""
    if len(matches) == 1:
        return f":{matches[0]} — {_COMMAND_HINTS.get(matches[0], '')}"
    return "possible: " + ", ".join(f":{m}" for m in matches)


# ── Command history persistence ───────────────────────────────────────────
# Append-only JSONL at .kairos/.tui_history, one record per submitted
# command line. Corrupt lines are skipped rather than sinking the whole
# file — this is a convenience log, not a source of truth.

HISTORY_FILENAME = ".tui_history"


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    timestamp: datetime
    command: str
    success: bool


def history_file_path(workspace_root: Path) -> Path:
    return workspace_root / ".kairos" / HISTORY_FILENAME


def load_history(workspace_root: Path) -> list[HistoryRecord]:
    path = history_file_path(workspace_root)
    if not path.exists():
        return []
    records: list[HistoryRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            records.append(
                HistoryRecord(
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    command=data["command"],
                    success=bool(data["success"]),
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return records


def append_history(workspace_root: Path, command: str, *, success: bool) -> None:
    path = history_file_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "command": command,
        "success": success,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def clear_history(workspace_root: Path) -> None:
    path = history_file_path(workspace_root)
    if path.exists():
        path.write_text("", encoding="utf-8")
