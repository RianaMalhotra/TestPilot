"""Track imported GitHub workflow runs uniquely.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "github_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository", sa.String(length=250), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.UniqueConstraint("repository", "workflow_run_id"),
    )


def downgrade():
    op.drop_table("github_imports")
