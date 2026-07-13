"""initial schema: nine core tables + FTS5 index and sync triggers

Revision ID: 0001
Revises:
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("sha256", sa.String, nullable=False),
        sa.Column("original_path", sa.Text, nullable=False),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("ingested_at", sa.DateTime, nullable=False),
        sa.Column("parser_name", sa.String, nullable=False),
        sa.Column("parser_version", sa.String, nullable=False),
        sa.Column("parse_status", sa.String, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256"], unique=True)
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"])

    op.create_table(
        "source_spans",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("artifact_id", sa.String, sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("span_kind", sa.String, nullable=False),
        sa.Column("locator_json", sa.JSON, nullable=False),
        sa.Column("parent_span_id", sa.String, sa.ForeignKey("source_spans.id"), nullable=True),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text_content", sa.Text, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_source_spans_artifact_id", "source_spans", ["artifact_id"])
    op.create_index("ix_source_spans_parent_span_id", "source_spans", ["parent_span_id"])

    op.create_table(
        "entities",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("canonical_name", sa.String, nullable=False),
        sa.Column("entity_type", sa.String, nullable=False),
        sa.Column("origin", sa.String, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_entities_canonical_name", "entities", ["canonical_name"])
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])

    op.create_table(
        "mentions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("entity_id", sa.String, sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("source_span_id", sa.String, sa.ForeignKey("source_spans.id"), nullable=False),
        sa.Column("surface_form", sa.String, nullable=False),
        sa.Column("extraction_rule", sa.String, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_mentions_entity_id", "mentions", ["entity_id"])
    op.create_index("ix_mentions_source_span_id", "mentions", ["source_span_id"])

    op.create_table(
        "relations",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("subject_id", sa.String, nullable=False),
        sa.Column("subject_kind", sa.String, nullable=False),
        sa.Column("predicate", sa.String, nullable=False),
        sa.Column("object_id", sa.String, nullable=False),
        sa.Column("object_kind", sa.String, nullable=False),
        sa.Column("evidence_span_id", sa.String, sa.ForeignKey("source_spans.id"), nullable=True),
        sa.Column("origin", sa.String, nullable=False),
        sa.Column("derivation_rule", sa.String, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_relations_subject_id", "relations", ["subject_id"])
    op.create_index("ix_relations_object_id", "relations", ["object_id"])
    op.create_index("ix_relations_predicate", "relations", ["predicate"])

    op.create_table(
        "notes",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("target_id", sa.String, nullable=False),
        sa.Column("target_kind", sa.String, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("supersedes_note_id", sa.String, sa.ForeignKey("notes.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_notes_target_id", "notes", ["target_id"])

    op.create_table(
        "coherence_wells",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_coherence_wells_name", "coherence_wells", ["name"], unique=True)

    op.create_table(
        "well_members",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("well_id", sa.String, sa.ForeignKey("coherence_wells.id"), nullable=False),
        sa.Column("target_id", sa.String, nullable=False),
        sa.Column("target_kind", sa.String, nullable=False),
        sa.Column("added_at", sa.DateTime, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_well_members_well_id", "well_members", ["well_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("payload_json", sa.JSON, nullable=False),
    )
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])
    op.create_index("ix_events_event_type", "events", ["event_type"])

    # --- FTS5 full-text index over source_spans.text_content ---
    # A standalone virtual table (not an ORM model — autogenerate cannot see
    # virtual tables), kept in sync by triggers so no write path can bypass
    # the index. span_id/artifact_id/span_kind are UNINDEXED: join keys and
    # pre-filters, not searched text.
    op.execute(
        """
        CREATE VIRTUAL TABLE source_spans_fts USING fts5(
            text_content,
            span_id UNINDEXED,
            artifact_id UNINDEXED,
            span_kind UNINDEXED
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_spans_fts_ai AFTER INSERT ON source_spans BEGIN
            INSERT INTO source_spans_fts(rowid, text_content, span_id, artifact_id, span_kind)
            VALUES (
                (SELECT COALESCE(MAX(rowid), 0) + 1 FROM source_spans_fts),
                new.text_content, new.id, new.artifact_id, new.span_kind
            );
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_spans_fts_ad AFTER DELETE ON source_spans BEGIN
            DELETE FROM source_spans_fts WHERE span_id = old.id;
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_spans_fts_au AFTER UPDATE ON source_spans BEGIN
            DELETE FROM source_spans_fts WHERE span_id = old.id;
            INSERT INTO source_spans_fts(rowid, text_content, span_id, artifact_id, span_kind)
            VALUES (
                (SELECT COALESCE(MAX(rowid), 0) + 1 FROM source_spans_fts),
                new.text_content, new.id, new.artifact_id, new.span_kind
            );
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS source_spans_fts_au")
    op.execute("DROP TRIGGER IF EXISTS source_spans_fts_ad")
    op.execute("DROP TRIGGER IF EXISTS source_spans_fts_ai")
    op.execute("DROP TABLE IF EXISTS source_spans_fts")
    op.drop_table("events")
    op.drop_table("well_members")
    op.drop_table("coherence_wells")
    op.drop_table("notes")
    op.drop_table("relations")
    op.drop_table("mentions")
    op.drop_table("entities")
    op.drop_table("source_spans")
    op.drop_table("artifacts")
