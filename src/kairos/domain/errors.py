"""Domain-level exceptions. CLI commands catch these and map them to non-zero exit codes.

Exit code taxonomy (see docs/cli.md):
    1 - expected user/input/domain failure (the default for KairosError)
    2 - workspace/configuration/integrity failure (overridden below)
    3 - unexpected internal error (not a KairosError at all; see cli/errors.py)
"""

from __future__ import annotations


class KairosError(Exception):
    """Base class for all expected, actionable KAIROS errors."""

    exit_code: int = 1


class WorkspaceNotFoundError(KairosError):
    """Raised when a command is run outside a directory containing ``.kairos/``."""

    exit_code = 2


class WorkspaceAlreadyExistsError(KairosError):
    """Raised by ``kairos init`` when a ``.kairos/`` directory already exists."""

    exit_code = 2


class ArtifactNotFoundError(KairosError):
    """Raised when an artifact id does not resolve to a known artifact."""


class SourcePathNotFoundError(KairosError):
    """Raised when an ingest path does not exist on disk."""


class InvalidLocatorError(KairosError):
    """Raised when a locator string cannot be parsed."""


class InvalidSearchQueryError(KairosError):
    """Raised when a query string is not valid FTS5 syntax."""


class NoParserAvailableError(KairosError):
    """Raised when no registered parser can handle a given file."""


class WellNotFoundError(KairosError):
    """Raised when a coherence well name does not exist."""


class WellAlreadyExistsError(KairosError):
    """Raised by ``kairos well create`` on a duplicate well name."""


class WellMemberNotFoundError(KairosError):
    """Raised by ``kairos well remove`` when the member is not in the well."""


class TargetNotFoundError(KairosError):
    """Raised when a note or well-add target id does not resolve to an artifact or span."""


class ConfigSymbolNotFoundError(KairosError):
    """Raised when ``kairos config`` is given a symbol name that was never ingested."""


class ReadOnlySourceViolationError(KairosError):
    """Raised if any code path attempts to mutate registered source material."""

    exit_code = 2
