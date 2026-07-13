"""The shared parser interface every corpus-native parser implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from kairos.domain.enums import ArtifactKind, ParseStatus
from kairos.domain.models import Diagnostic, Entity, Mention, Relation, SourceSpan


@dataclass(slots=True)
class ParseResult:
    """Everything a parser produces from one artifact.

    A parser never raises to signal malformed input: it downgrades
    ``parse_status`` to ``partial`` or ``failed``, records a ``Diagnostic``,
    and returns whatever it could recover. Nothing is silently discarded.
    """

    spans: list[SourceSpan] = field(default_factory=lambda: list[SourceSpan]())
    entities: list[Entity] = field(default_factory=lambda: list[Entity]())
    mentions: list[Mention] = field(default_factory=lambda: list[Mention]())
    relations: list[Relation] = field(default_factory=lambda: list[Relation]())
    diagnostics: list[Diagnostic] = field(default_factory=lambda: list[Diagnostic]())
    parse_status: ParseStatus = ParseStatus.OK
    artifact_metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


class Parser(Protocol):
    """Deterministic parser: same bytes in, same ``ParseResult`` shape out."""

    kind: ArtifactKind
    parser_name: str
    parser_version: str

    def sniff(self, path: Path) -> bool:
        """Return True if this parser can handle the file at ``path``."""
        ...

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        """Parse the file at ``path``, whose artifact id is already assigned."""
        ...
