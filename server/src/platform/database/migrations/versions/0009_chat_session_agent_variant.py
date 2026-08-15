"""Persist the selected chat-session agent variant."""
from alembic import op
import sqlalchemy as sa

revision = "0009_chat_session_agent_variant"
down_revision = "0008_chat_session_cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_session",
        sa.Column("agent_variant", sa.String(), nullable=True, server_default="direct-mini"),
    )
    op.execute("UPDATE chat_session SET agent_variant = 'direct-mini' WHERE agent_variant IS NULL")
    op.alter_column("chat_session", "agent_variant", nullable=False)
    op.create_index("ix_chat_session_agent_variant", "chat_session", ["agent_variant"])


def downgrade() -> None:
    op.drop_index("ix_chat_session_agent_variant", table_name="chat_session")
    op.drop_column("chat_session", "agent_variant")
