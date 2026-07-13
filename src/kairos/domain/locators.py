"""Locator value objects: the exact, source-appropriate pointer into an artifact.

Every locator serializes to a compact string form (``to_str``) and parses
back from that same form (``parse_locator_str``), because ``kairos show
--locator <str>`` takes the string form straight from the CLI and
``ProvenanceEnvelope.locator_str`` round-trips it back out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import cast

from kairos.domain.enums import LocatorKind
from kairos.domain.errors import InvalidLocatorError


@dataclass(frozen=True, slots=True)
class PdfPageLocator:
    kind: LocatorKind = LocatorKind.PDF_PAGE
    page: int = 0

    def to_str(self) -> str:
        return f"page:{self.page}"


@dataclass(frozen=True, slots=True)
class LineRangeLocator:
    start_line: int
    end_line: int
    kind: LocatorKind = LocatorKind.LINE_RANGE

    def to_str(self) -> str:
        return f"lines:{self.start_line}-{self.end_line}"


@dataclass(frozen=True, slots=True)
class JsonPathLocator:
    json_path: str
    kind: LocatorKind = LocatorKind.JSON_PATH

    def to_str(self) -> str:
        return f"json:{self.json_path}"


@dataclass(frozen=True, slots=True)
class KconfigSymbolLocator:
    menu_path: str
    kind: LocatorKind = LocatorKind.KCONFIG_SYMBOL

    def to_str(self) -> str:
        return f"kconfig:{self.menu_path}"


@dataclass(frozen=True, slots=True)
class RepoFileLinesLocator:
    file_path: str
    start_line: int
    end_line: int
    kind: LocatorKind = LocatorKind.REPO_FILE_LINES

    def to_str(self) -> str:
        return f"repo:{self.file_path}:{self.start_line}-{self.end_line}"


@dataclass(frozen=True, slots=True)
class LogEventLocator:
    line_number: int
    timestamp: str | None
    kind: LocatorKind = LocatorKind.LOG_EVENT

    def to_str(self) -> str:
        ts = self.timestamp or ""
        return f"log:{self.line_number}:{ts}"


Locator = (
    PdfPageLocator
    | LineRangeLocator
    | JsonPathLocator
    | KconfigSymbolLocator
    | RepoFileLinesLocator
    | LogEventLocator
)

_PAGE_RE = re.compile(r"^page:(\d+)$")
_LINES_RE = re.compile(r"^lines:(\d+)-(\d+)$")
_JSON_RE = re.compile(r"^json:(.+)$")
_KCONFIG_RE = re.compile(r"^kconfig:(.+)$")
_REPO_RE = re.compile(r"^repo:(.+):(\d+)-(\d+)$")
_LOG_RE = re.compile(r"^log:(\d+):(.*)$")


def parse_locator_str(text: str) -> Locator:
    """Parse a locator's compact string form back into a value object."""
    if m := _PAGE_RE.match(text):
        return PdfPageLocator(page=int(m.group(1)))
    if m := _LINES_RE.match(text):
        return LineRangeLocator(start_line=int(m.group(1)), end_line=int(m.group(2)))
    if m := _JSON_RE.match(text):
        return JsonPathLocator(json_path=m.group(1))
    if m := _KCONFIG_RE.match(text):
        return KconfigSymbolLocator(menu_path=m.group(1))
    if m := _REPO_RE.match(text):
        return RepoFileLinesLocator(
            file_path=m.group(1), start_line=int(m.group(2)), end_line=int(m.group(3))
        )
    if m := _LOG_RE.match(text):
        return LogEventLocator(line_number=int(m.group(1)), timestamp=m.group(2) or None)
    raise InvalidLocatorError(f"Unrecognized locator string: {text!r}")


def locator_to_json(locator: Locator) -> dict[str, object]:
    """Serialize a locator to the JSON form stored in ``source_spans.locator_json``."""
    data: dict[str, object] = {
        f.name: getattr(locator, f.name) for f in fields(locator) if f.name != "kind"
    }
    data["kind"] = locator.kind.value
    return data


def _as_int(data: dict[str, object], key: str) -> int:
    """``locator_json`` round-trips through SQLite JSON, so these are always
    plain ints at runtime; ``cast`` documents that invariant for the type
    checker rather than re-validating it on every read.
    """
    return int(cast(int, data[key]))


def locator_from_json(data: dict[str, object]) -> Locator:
    kind = LocatorKind(data["kind"])
    match kind:
        case LocatorKind.PDF_PAGE:
            return PdfPageLocator(page=_as_int(data, "page"))
        case LocatorKind.LINE_RANGE:
            return LineRangeLocator(
                start_line=_as_int(data, "start_line"),
                end_line=_as_int(data, "end_line"),
            )
        case LocatorKind.JSON_PATH:
            return JsonPathLocator(json_path=str(data["json_path"]))
        case LocatorKind.KCONFIG_SYMBOL:
            return KconfigSymbolLocator(menu_path=str(data["menu_path"]))
        case LocatorKind.REPO_FILE_LINES:
            return RepoFileLinesLocator(
                file_path=str(data["file_path"]),
                start_line=_as_int(data, "start_line"),
                end_line=_as_int(data, "end_line"),
            )
        case LocatorKind.LOG_EVENT:
            ts = data.get("timestamp")
            return LogEventLocator(
                line_number=_as_int(data, "line_number"),
                timestamp=str(ts) if ts is not None else None,
            )
    raise InvalidLocatorError(f"Unhandled locator kind: {kind}")
