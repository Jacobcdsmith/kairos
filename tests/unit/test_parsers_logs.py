"""Runtime/emulator log parser: line spans, session boundaries, malformed lines."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.enums import EntityType, ParseStatus, SpanKind
from kairos.infrastructure.parsers.logs import LogParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "logs"


def test_log_lines_get_timestamp_level_component() -> None:
    parser = LogParser()
    result = parser.parse(FIXTURES / "sample.log", "artifact-log")

    matched = [s for s in result.spans if s.metadata.get("level") == "INFO"]
    assert matched
    assert matched[0].metadata["component"] in {"boot", "wifi"}


def test_unmatched_line_still_gets_a_span_with_diagnostic() -> None:
    parser = LogParser()
    result = parser.parse(FIXTURES / "sample.log", "artifact-log")

    assert result.parse_status == ParseStatus.PARTIAL
    unmatched = [
        s
        for s in result.spans
        if s.metadata.get("level") is None and not s.metadata.get("is_session_boundary")
    ]
    assert len(unmatched) == 1
    assert "not a well formed" in unmatched[0].text_content
    assert result.diagnostics


def test_session_boundary_creates_entity_and_relations() -> None:
    parser = LogParser()
    result = parser.parse(FIXTURES / "sample.log", "artifact-log")

    sessions = [e for e in result.entities if e.entity_type == EntityType.LOG_SESSION.value]
    assert len(sessions) == 1
    assert sessions[0].canonical_name == "BOOT"

    membership = [r for r in result.relations if r.predicate == "log_in_session"]
    assert len(membership) == 4  # every line after the boundary (not the boundary itself)
    assert all(r.subject_id == sessions[0].id for r in membership)


def test_session_boundary_is_grounded_by_a_mention() -> None:
    """The boundary line itself is the session entity's evidence trail —
    without this, a log_session entity would be the only extracted-layer
    entity in the codebase with no span backing its existence at all.
    """
    parser = LogParser()
    result = parser.parse(FIXTURES / "sample.log", "artifact-log")

    session_entity = next(
        e for e in result.entities if e.entity_type == EntityType.LOG_SESSION.value
    )
    mentions = [m for m in result.mentions if m.entity_id == session_entity.id]
    assert len(mentions) == 1
    boundary_span = next(s for s in result.spans if s.id == mentions[0].source_span_id)
    assert boundary_span.metadata.get("is_session_boundary") is True
    assert boundary_span.text_content == "=== BOOT ==="


def test_all_lines_produce_log_line_spans() -> None:
    parser = LogParser()
    result = parser.parse(FIXTURES / "sample.log", "artifact-log")

    assert all(s.span_kind == SpanKind.LOG_LINE for s in result.spans)
    assert len(result.spans) == 5  # every line, including the session boundary marker
