"""KAIROS Framework — local-first, terminal-native workspace for a persistent agent runtime."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth is pyproject.toml's [project] version; this
    # reads it back from the installed package's metadata rather than
    # duplicating the literal string here.
    __version__ = version("kairos")
except PackageNotFoundError:
    # Only reachable if kairos is imported without being installed at all
    # (e.g. by manipulating sys.path directly) — not a supported configuration.
    __version__ = "0+unknown"
