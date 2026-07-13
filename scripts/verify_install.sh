#!/usr/bin/env bash
# Proves the BUILT distribution artifacts (wheel and sdist), not the repo
# checkout, install cleanly and run correctly.
#
# For each artifact this:
#   1. creates a fresh, throwaway virtual environment;
#   2. installs only that one artifact into it (no `-e`, no repo on
#      sys.path);
#   3. asserts the `kairos` module Python actually imports resolves into
#      that venv's site-packages, not into this repository's src/ tree;
#   4. runs a minimal offline workflow through the installed `kairos`
#      command: init, ingest, search, show, trace, doctor;
#   5. tears down its temporary venv and workspace.
#
# KAIROS makes zero network calls by design; the authoritative, code-level
# proof of that is tests/integration/test_offline.py (a socket-level
# monkeypatch across the full command surface). This script adds a cheap
# additional guard for its own workflow steps (bogus proxy env vars) — belt
# and suspenders, not the primary evidence.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES="$REPO_ROOT/tests/fixtures"
PYTHON_BIN="${PYTHON_BIN:-}"

if [ -z "$PYTHON_BIN" ]; then
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" --version >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi

step() {
    echo
    echo "=== $* ==="
}

step "build sdist + wheel"
rm -rf "$REPO_ROOT/dist"
(cd "$REPO_ROOT" && "$PYTHON_BIN" -m build --no-isolation)

WHEEL="$(ls "$REPO_ROOT"/dist/*.whl | head -n1)"
SDIST="$(ls "$REPO_ROOT"/dist/*.tar.gz | head -n1)"
echo "wheel: $WHEEL"
echo "sdist: $SDIST"

verify_artifact() {
    local artifact="$1"
    local label="$2"
    local tmp_root venv_dir workdir_root workdir venv_py venv_kairos artifact_id

    tmp_root="$(mktemp -d)"
    venv_dir="$tmp_root/venv"

    step "$label: create a fresh venv and install only this artifact"
    "$PYTHON_BIN" -m venv "$venv_dir"

    if [ -f "$venv_dir/Scripts/python.exe" ]; then
        venv_py="$venv_dir/Scripts/python.exe"
        venv_kairos="$venv_dir/Scripts/kairos.exe"
    else
        venv_py="$venv_dir/bin/python"
        venv_kairos="$venv_dir/bin/kairos"
    fi

    "$venv_py" -m pip install --quiet --upgrade pip
    "$venv_py" -m pip install --quiet "$artifact"

    step "$label: confirm the installed module is not this repo checkout"
    "$venv_py" -c "
import pathlib
import kairos
resolved = pathlib.Path(kairos.__file__).resolve()
repo_src = pathlib.Path(r'$REPO_ROOT').resolve() / 'src'
assert repo_src not in resolved.parents, (
    f'{resolved} resolves inside the repo checkout, not an installed site-packages tree'
)
print('kairos module resolved to:', resolved)
"

    step "$label: kairos --version"
    "$venv_kairos" --version

    step "$label: minimal offline workflow (init/ingest/search/show/trace/doctor)"
    workdir_root="$(mktemp -d)"
    workdir="$workdir_root/kairos-verify-workspace"

    # Belt-and-suspenders network guard for this workflow (see file header
    # for the authoritative, code-level proof this relies on instead).
    export http_proxy="http://127.0.0.1:1" https_proxy="http://127.0.0.1:1"

    "$venv_kairos" init "$workdir"
    (
        cd "$workdir"
        "$venv_kairos" ingest "$FIXTURES/text/sample.md"
        "$venv_kairos" search widget
        artifact_id=$("$venv_py" -c "
import sqlite3
conn = sqlite3.connect('.kairos/kairos.db')
print(conn.execute('SELECT id FROM artifacts LIMIT 1').fetchone()[0])
")
        "$venv_kairos" show "$artifact_id"
        "$venv_kairos" trace Widgets --depth 2
        "$venv_kairos" doctor
    )

    unset http_proxy https_proxy
    rm -rf "$tmp_root" "$workdir_root"
    echo "$label: OK — installed distribution verified independently of the repo checkout."
}

verify_artifact "$WHEEL" "wheel"
verify_artifact "$SDIST" "sdist"

step "done"
echo "Artifact-install verification passed for both the wheel and the sdist."
