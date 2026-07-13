#!/usr/bin/env bash
# Scripted walkthrough of every KAIROS v0.1 command, against the synthetic
# fixtures in tests/fixtures/. Safe to re-run: it creates a fresh temp
# workspace each time.
set -euo pipefail

KAIROS_BIN="${KAIROS_BIN:-kairos}"

if [ -z "${PYTHON_BIN:-}" ]; then
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" --version >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES="$REPO_ROOT/tests/fixtures"
WORKSPACE="$(mktemp -d)/demo-workspace"

step() {
    echo
    echo "=== $* ==="
}

step "init"
"$KAIROS_BIN" init "$WORKSPACE"
cd "$WORKSPACE"

step "ingest: markdown"
"$KAIROS_BIN" ingest "$FIXTURES/text/sample.md"
"$KAIROS_BIN" ingest "$FIXTURES/text/sample2.md"

step "ingest: json"
"$KAIROS_BIN" ingest "$FIXTURES/json/sample.json"

step "ingest: kconfig-menu json"
"$KAIROS_BIN" ingest "$FIXTURES/kconfig/sample_menu.json"

step "ingest: log"
"$KAIROS_BIN" ingest "$FIXTURES/logs/sample.log"

step "ingest: python repository files (--recursive)"
"$KAIROS_BIN" ingest "$FIXTURES/repo" --recursive

step "ingest: pdf"
"$KAIROS_BIN" ingest "$FIXTURES/pdf/sample.pdf"

step "artifacts"
"$KAIROS_BIN" artifacts

step "search"
"$KAIROS_BIN" search widget

step "show (first markdown artifact)"
ARTIFACT_ID=$("$PYTHON_BIN" -c "
import sqlite3
conn = sqlite3.connect('.kairos/kairos.db')
print(conn.execute(\"SELECT id FROM artifacts WHERE kind='markdown' LIMIT 1\").fetchone()[0])
")
"$KAIROS_BIN" show "$ARTIFACT_ID"

step "trace: crosses artifacts via a shared heading"
"$KAIROS_BIN" trace gadgets --depth 3

step "config: kconfig symbol lookup"
"$KAIROS_BIN" config CONFIG_WIFI_POWER_SAVE

step "logs: search with context and level filter"
"$KAIROS_BIN" logs widget --before 1 --after 1
"$KAIROS_BIN" logs connection --level ERROR

step "note: add and list"
"$KAIROS_BIN" note add "$ARTIFACT_ID" "revisit after v0.2"
"$KAIROS_BIN" note list "$ARTIFACT_ID"

step "well: create, add, show, list"
"$KAIROS_BIN" well create widget-work --purpose "Everything about the widget system"
"$KAIROS_BIN" well add widget-work "$ARTIFACT_ID" --note "primary doc"
"$KAIROS_BIN" well show widget-work
"$KAIROS_BIN" well list

step "search scoped to a well"
"$KAIROS_BIN" search widget --well widget-work

step "doctor"
"$KAIROS_BIN" doctor

step "done"
echo "Workspace left at: $WORKSPACE"
