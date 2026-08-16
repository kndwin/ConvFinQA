"""Rename the public approach and pin execution configuration."""

import sqlalchemy as sa
from alembic import op

# Keep this within alembic_version.version_num's VARCHAR(32) limit.
revision = "0011_chat_session_approach_v1"
down_revision = "0010_chat_session_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_chat_session_agent_variant", table_name="chat_session")
    op.alter_column("chat_session", "agent_variant", new_column_name="agent_approach")
    op.execute(
        "UPDATE chat_session SET agent_approach = 'baseline' WHERE agent_approach = 'direct-mini'"
    )
    op.execute(
        "UPDATE chat_session SET agent_approach = 'baseline-tool' "
        "WHERE agent_approach = 'calculator-mini'"
    )
    op.execute(
        "UPDATE chat_session SET agent_approach = 'baseline' "
        "WHERE agent_approach NOT IN ('baseline', 'baseline-tool')"
    )
    op.alter_column("chat_session", "agent_approach", server_default="baseline")
    op.create_index("ix_chat_session_agent_approach", "chat_session", ["agent_approach"])
    op.add_column(
        "chat_session",
        sa.Column("prompt_version", sa.String(), nullable=True, server_default="baseline:v1"),
    )
    op.add_column(
        "chat_session",
        sa.Column(
            "context_version", sa.String(), nullable=True, server_default="document-conversation:v1"
        ),
    )
    # Legacy unknown approaches are deliberately pinned to the safe baseline.
    op.execute(
        "UPDATE chat_session SET prompt_version = CASE "
        "WHEN agent_approach = 'baseline-tool' THEN 'baseline-tool:v1' "
        "ELSE 'baseline:v1' END, context_version = 'document-conversation:v1'"
    )
    op.alter_column("chat_session", "prompt_version", nullable=False)
    op.alter_column("chat_session", "context_version", nullable=False)


def downgrade() -> None:
    op.drop_column("chat_session", "context_version")
    op.drop_column("chat_session", "prompt_version")
    op.drop_index("ix_chat_session_agent_approach", table_name="chat_session")
    op.alter_column("chat_session", "agent_approach", server_default="direct-mini")
    op.execute(
        "UPDATE chat_session SET agent_approach = 'direct-mini' WHERE agent_approach = 'baseline'"
    )
    op.execute(
        "UPDATE chat_session SET agent_approach = 'calculator-mini' "
        "WHERE agent_approach = 'baseline-tool'"
    )
    op.alter_column("chat_session", "agent_approach", new_column_name="agent_variant")
    op.create_index("ix_chat_session_agent_variant", "chat_session", ["agent_variant"])
