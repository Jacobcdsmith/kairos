"""Wires infrastructure into one object services take as their first argument."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from kairos.infrastructure.database.engine import make_engine, make_session_factory
from kairos.infrastructure.database.migrate import upgrade_to_head
from kairos.infrastructure.filesystem.content_store import ContentStore
from kairos.infrastructure.filesystem.workspace import Workspace, find_workspace, init_workspace
from kairos.infrastructure.parsers.registry import ParserRegistry


@dataclass(slots=True)
class RuntimeContext:
    workspace: Workspace
    session_factory: sessionmaker[Session]
    content_store: ContentStore
    parser_registry: ParserRegistry

    @classmethod
    def open(cls, start: Path) -> RuntimeContext:
        workspace = find_workspace(start)
        engine = make_engine(workspace.db_path)
        return cls(
            workspace=workspace,
            session_factory=make_session_factory(engine),
            content_store=ContentStore(workspace.content_dir),
            parser_registry=ParserRegistry(),
        )

    @classmethod
    def create(cls, root: Path, *, name: str | None = None) -> RuntimeContext:
        workspace = init_workspace(root, name=name)
        upgrade_to_head(workspace.db_path)
        engine = make_engine(workspace.db_path)
        return cls(
            workspace=workspace,
            session_factory=make_session_factory(engine),
            content_store=ContentStore(workspace.content_dir),
            parser_registry=ParserRegistry(),
        )
