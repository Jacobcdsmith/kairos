"""Engine/session construction and the FTS5 capability check used by ``kairos doctor``."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def _enable_sqlite_pragmas(
    dbapi_connection: sqlite3.Connection, _connection_record: object
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def make_engine(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    event.listen(engine, "connect", _enable_sqlite_pragmas)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def fts5_is_available() -> bool:
    """Verify this Python's sqlite3 build actually has FTS5 compiled in.

    Used by ``kairos doctor`` — the one environment failure that would
    otherwise break every ingest and search silently at first use.
    """
    try:
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE VIRTUAL TABLE _kairos_fts5_probe USING fts5(x)")
            conn.execute("DROP TABLE _kairos_fts5_probe")
            return True
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return False
