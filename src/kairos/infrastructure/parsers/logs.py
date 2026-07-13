"""Runtime/emulator log parser.

One span per line, with a ``log_event`` locator (line number + timestamp
when present). Lines matching the default pattern
``<timestamp> <LEVEL> [component] message`` are extracted with
timestamp/level/component split out; lines that don't match still get a
span (fields left ``None``) plus a diagnostic — never dropped. A session
boundary line (``=== <label> ===``) starts a new ``log_session`` entity;
every line span until the next boundary gets a ``log_in_session`` derived
relation to it, evidenced by that line's own span.
"""

from __future__ import annotations

import re
from pathlib import Path

from kairos.domain.enums import (
    ArtifactKind,
    EntityType,
    Origin,
    ParseStatus,
    RelationPredicate,
    SpanKind,
)
from kairos.domain.ids import new_id
from kairos.domain.locators import LogEventLocator, locator_to_json
from kairos.domain.models import Diagnostic, Entity, Relation, SourceSpan
from kairos.domain.parser import ParseResult

_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+(?P<level>[A-Z]+)\s+\[(?P<component>[^\]]+)\]\s+(?P<message>.*)$"
)
_SESSION_BOUNDARY_RE = re.compile(r"^===\s*(?P<label>.+?)\s*===$")


class LogParser:
    kind = ArtifactKind.LOG
    parser_name = "kairos.log"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        return path.suffix.lower() in {".log", ".logs"}

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        result = ParseResult()
        raw = path.read_bytes().decode("utf-8", errors="replace")
        lines = raw.splitlines()

        current_session_entity_id: str | None = None
        any_unmatched = False

        for i, line in enumerate(lines):
            line_number = i + 1

            if boundary := _SESSION_BOUNDARY_RE.match(line.strip()):
                session_entity_id = new_id()
                result.entities.append(
                    Entity(
                        id=session_entity_id,
                        canonical_name=boundary.group("label"),
                        entity_type=EntityType.LOG_SESSION.value,
                        origin=Origin.EXTRACTED,
                    )
                )
                current_session_entity_id = session_entity_id
                continue

            match = _LOG_LINE_RE.match(line)
            span_id = new_id()
            if match:
                timestamp = match.group("timestamp")
                level = match.group("level")
                component = match.group("component")
                message = match.group("message")
            else:
                timestamp = None
                level = None
                component = None
                message = line
                any_unmatched = True
                result.diagnostics.append(
                    Diagnostic(
                        message=f"Line {line_number} did not match the log line pattern",
                        locator_json=locator_to_json(
                            LogEventLocator(line_number=line_number, timestamp=None)
                        ),
                    )
                )

            locator = LogEventLocator(line_number=line_number, timestamp=timestamp)
            result.spans.append(
                SourceSpan(
                    id=span_id,
                    artifact_id=artifact_id,
                    span_kind=SpanKind.LOG_LINE,
                    locator_json=locator_to_json(locator),
                    parent_span_id=None,
                    ordinal=i,
                    text_content=message,
                    metadata={"level": level, "component": component, "timestamp": timestamp},
                )
            )

            if current_session_entity_id is not None:
                result.relations.append(
                    Relation(
                        id=new_id(),
                        subject_id=current_session_entity_id,
                        subject_kind="entity",
                        predicate=RelationPredicate.LOG_IN_SESSION.value,
                        object_id=span_id,
                        object_kind="span",
                        evidence_span_id=span_id,
                        origin=Origin.DERIVED,
                        derivation_rule="log.session_membership.v1",
                        confidence=1.0,
                    )
                )

        result.parse_status = ParseStatus.PARTIAL if any_unmatched else ParseStatus.OK
        return result
