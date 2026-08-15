"""Make message deduplication session scoped and remove redundant indexes."""
from alembic import op
import sqlalchemy as sa

revision = "0005_chat_message_constraints"
down_revision = "0004_chat_messages_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_agent_run_run_id", table_name="agent_run")
    op.drop_index("ix_chat_message_client_message_id", table_name="chat_message")
    op.create_unique_constraint(
        "uq_chat_message_session_client_id",
        "chat_message",
        ["chat_session_id", "client_message_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_chat_message_session_client_id", "chat_message", type_="unique")
    op.create_index("ix_chat_message_client_message_id", "chat_message", ["client_message_id"])
    op.create_index("ix_agent_run_run_id", "agent_run", ["run_id"])
