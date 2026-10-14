"""Create projects, test runs, and AI analyses."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("projects",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False), sa.Column("project_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_projects_name", "projects", ["name"], unique=True)
    op.create_table("test_runs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False), sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False), sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False), sa.Column("output", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_test_runs_project_id", "test_runs", ["project_id"])
    op.create_table("analyses", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_analyses_run_id", "analyses", ["run_id"])

def downgrade():
    op.drop_table("analyses")
    op.drop_table("test_runs")
    op.drop_table("projects")

