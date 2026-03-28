"""Initial schemas — asha_health and lawyer_ai tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ASHA Health schema ---
    op.execute("CREATE SCHEMA IF NOT EXISTS asha_health")

    op.create_table(
        "workers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("phone", sa.String(15), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), server_default="hi"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="asha_health",
    )

    op.create_table(
        "visits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("worker_id", UUID(as_uuid=True), sa.ForeignKey("asha_health.workers.id"), nullable=True),
        sa.Column("patient_name", sa.String(100), nullable=True),
        sa.Column("patient_age", sa.Integer, nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("complaint", sa.Text, nullable=True),
        sa.Column("temperature", sa.Numeric(4, 1), nullable=True),
        sa.Column("weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("visit_date", sa.Date, server_default=sa.text("CURRENT_DATE")),
        sa.Column("referral_needed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("raw_transcript", sa.Text, nullable=True),
        sa.Column("sync_status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="asha_health",
    )

    op.create_index(
        "ix_visits_worker_date",
        "visits",
        ["worker_id", "visit_date"],
        schema="asha_health",
    )
    op.create_index(
        "ix_visits_sync_status",
        "visits",
        ["sync_status"],
        schema="asha_health",
    )

    # --- Lawyer AI schema ---
    op.execute("CREATE SCHEMA IF NOT EXISTS lawyer_ai")

    op.create_table(
        "queries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("query_text", sa.Text, nullable=True),
        sa.Column("response_text", sa.Text, nullable=True),
        sa.Column("sections_cited", sa.Text, nullable=True),
        sa.Column("severity", sa.String(10), nullable=True),
        sa.Column("language", sa.String(10), server_default="hi"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="lawyer_ai",
    )


def downgrade() -> None:
    op.drop_table("queries", schema="lawyer_ai")
    op.execute("DROP SCHEMA IF EXISTS lawyer_ai")

    op.drop_index("ix_visits_sync_status", table_name="visits", schema="asha_health")
    op.drop_index("ix_visits_worker_date", table_name="visits", schema="asha_health")
    op.drop_table("visits", schema="asha_health")
    op.drop_table("workers", schema="asha_health")
    op.execute("DROP SCHEMA IF EXISTS asha_health")
