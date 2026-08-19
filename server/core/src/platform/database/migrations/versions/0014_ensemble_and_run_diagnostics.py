"""Persist ensemble pins and durable run diagnostics from the current head."""

from alembic import op
import sqlalchemy as sa


revision = "0014_ensemble_runs"
down_revision = "0013_chat_session_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_session", sa.Column("ensemble_config_json", sa.Text(), nullable=True))
    op.add_column("agent_run", sa.Column("diagnostics_json", sa.Text(), nullable=True))
    op.add_column("agent_run", sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_agent_run_temporal_workflow_id", "agent_run", ["temporal_workflow_id"])


def downgrade() -> None:
    op.drop_constraint("uq_agent_run_temporal_workflow_id", "agent_run", type_="unique")
    op.drop_column("agent_run", "temporal_workflow_id")
    op.drop_column("agent_run", "diagnostics_json")
    op.drop_column("chat_session", "ensemble_config_json")
