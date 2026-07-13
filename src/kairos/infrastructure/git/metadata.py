"""Read-only Git metadata extraction. Never mutates the target repository.

Failures (not a git repo, git not installed, detached weirdness) are
non-fatal: callers get ``None`` and ingestion proceeds without git metadata.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitMetadata:
    branch: str | None
    commit: str | None
    remote_url: str | None


def _run(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def read_git_metadata(path: Path) -> GitMetadata | None:
    """Read branch/commit/remote for the git working tree containing ``path``, if any."""
    directory = path if path.is_dir() else path.parent
    inside = _run(["git", "rev-parse", "--is-inside-work-tree"], directory)
    if inside != "true":
        return None

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], directory)
    commit = _run(["git", "rev-parse", "HEAD"], directory)
    remote_url = _run(["git", "remote", "get-url", "origin"], directory)

    return GitMetadata(branch=branch, commit=commit, remote_url=remote_url)
