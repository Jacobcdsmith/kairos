"""Programmatic Alembic invocation — ``kairos init`` calls this directly, never a subprocess."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _config_for(db_path: Path) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def upgrade_to_head(db_path: Path) -> None:
    command.upgrade(_config_for(db_path), "head")
