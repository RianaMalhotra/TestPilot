"""Store historical API latency measurements.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "performance_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commit_sha", sa.String(100), nullable=False),
        sa.Column("branch", sa.String(200), nullable=False),
        sa.Column("method", sa.String(12), nullable=False),
        sa.Column("route", sa.String(500), nullable=False),
        sa.Column("p95_ms", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("performance_samples")
