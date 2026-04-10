"""Add model_configs table for multi-provider LLM routing.

Revision ID: 002_model_configs
Revises: 001_initial_schemas
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002_model_configs"
down_revision = "001_initial_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_configs",
        sa.Column("app_id", sa.String(50), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("temperature", sa.Float, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, server_default="2048"),
        sa.Column("fallback_chain", JSONB, server_default="[]"),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("model_configs")
