"""Controlled vocabularies used throughout the domain and schema layers."""

from __future__ import annotations

from enum import StrEnum


class ArtifactKind(StrEnum):
    """The kind of a top-level ingested artifact."""

    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"
    KCONFIG = "kconfig"
    LOG = "log"
    REPOSITORY = "repository"
    REPOSITORY_FILE = "repository_file"


class SpanKind(StrEnum):
    """The structural kind of a source span, independent of artifact kind."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    LINK = "link"
    PDF_PAGE = "pdf_page"
    JSON_SCALAR = "json_scalar"
    JSON_CONTAINER = "json_container"
    KCONFIG_MENU = "kconfig_menu"
    KCONFIG_SYMBOL = "kconfig_symbol"
    LOG_LINE = "log_line"
    MODULE = "module"
    CLASS_DEF = "class_def"
    FUNCTION_DEF = "function_def"
    IMPORT = "import"
    FILE = "file"


class ParseStatus(StrEnum):
    """Outcome of parsing a single artifact. Never silently discarded."""

    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class Origin(StrEnum):
    """The four-way (plus reserved fifth) provenance classification.

    Nothing in v0.1 may be presented as source truth unless it truly is one
    of these. ``MODEL`` is reserved for a future milestone with model
    inference; no code path in v0.1 writes it.
    """

    RAW = "raw"
    EXTRACTED = "extracted"
    DERIVED = "derived"
    USER = "user"
    MODEL = "model"


class EntityType(StrEnum):
    HEADING = "heading"
    MODULE = "module"
    CLASS_DEF = "class_def"
    FUNCTION_DEF = "function_def"
    KCONFIG_SYMBOL = "kconfig_symbol"
    LOG_SESSION = "log_session"
    JSON_NODE = "json_node"
    TERM = "term"


class RelationPredicate(StrEnum):
    """Derivation rules for machine-created links between source objects."""

    HEADING_CONTAINS = "heading_contains"
    PAGE_PRECEDES = "page_precedes"
    JSON_CONTAINS = "json_contains"
    MENU_CONTAINS = "menu_contains"
    DEPENDS_ON = "depends_on"
    LOG_IN_SESSION = "log_in_session"
    IMPORTS = "imports"


class LocatorKind(StrEnum):
    PDF_PAGE = "pdf_page"
    LINE_RANGE = "line_range"
    JSON_PATH = "json_path"
    KCONFIG_SYMBOL = "kconfig_symbol"
    REPO_FILE_LINES = "repo_file_lines"
    LOG_EVENT = "log_event"
