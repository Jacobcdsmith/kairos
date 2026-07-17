"""The Terminal Lineage Interface (TLI) — ``kairos tui``, v0.2-alpha.

A Textual presentation layer over the existing v0.1 service layer. Nothing
here may import SQLAlchemy, the FTS layer, or a parser directly; every
query goes through ``kairos.services.*``. See
docs/tli-implementation-plan.md for the full design.

Textual is an optional dependency. Only this package (and code imported
from within it) may import ``textual``.
"""

from __future__ import annotations
