"""Make agent run timestamps timezone-aware."""

from alembic import op
import sqlalchemy as sa


revision = "0007_agent_run_timestamps"
down_revision = "0006_agent_run_assistant_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "agent_run",
        "started_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "agent_run",
        "completed_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "agent_run",
        "started_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "agent_run",
        "completed_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
