"""Domain-level exceptions. CLI commands catch these and map them to non-zero exit codes."""

from __future__ import annotations


class KairosError(Exception):
    """Base class for all expected, actionable KAIROS errors."""


class WorkspaceNotFoundError(KairosError):
    """Raised when a command is run outside a directory containing ``.kairos/``."""


class WorkspaceAlreadyExistsError(KairosError):
    """Raised by ``kairos init`` when a ``.kairos/`` directory already exists."""


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
