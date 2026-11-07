"""Create TestPilot schema for new databases.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commit_sha", sa.String(length=100), nullable=False),
        sa.Column("branch", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("test_name", sa.String(length=500), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
    )
    op.create_index("ix_results_test_name", "results", ["test_name"])


def downgrade():
    op.drop_index("ix_results_test_name", table_name="results")
    op.drop_table("results")
    op.drop_table("runs")
