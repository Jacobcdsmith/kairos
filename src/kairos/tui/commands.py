"""The TUI's explicit command grammar: ``:name arg1 arg2...``. Not a
natural-language parser — unknown input is a parse error, not a best-effort
guess.
"""

from __future__ import annotations

from dataclasses import dataclass

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
