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
    unmatched = [s for s in result.spans if s.metadata.get("level") is None]
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
    assert len(membership) == 4  # every line after the boundary
    assert all(r.subject_id == sessions[0].id for r in membership)


def test_all_lines_produce_log_line_spans() -> None:
    parser = LogParser()
    result = parser.parse(FIXTURES / "sample.log", "artifact-log")

    assert all(s.span_kind == SpanKind.LOG_LINE for s in result.spans)
    assert len(result.spans) == 4  # boundary line itself is not a span
