"""Cascade dependent transcript and run rows when deleting a session."""
from alembic import op

revision = "0008_chat_session_cascade"
down_revision = "0007_agent_run_timestamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("chat_message_chat_session_id_fkey", "chat_message", type_="foreignkey")
    op.drop_constraint("agent_run_chat_session_id_fkey", "agent_run", type_="foreignkey")
    op.create_foreign_key("chat_message_chat_session_id_fkey", "chat_message", "chat_session", ["chat_session_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("agent_run_chat_session_id_fkey", "agent_run", "chat_session", ["chat_session_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("chat_message_chat_session_id_fkey", "chat_message", type_="foreignkey")
    op.drop_constraint("agent_run_chat_session_id_fkey", "agent_run", type_="foreignkey")
    op.create_foreign_key("chat_message_chat_session_id_fkey", "chat_message", "chat_session", ["chat_session_id"], ["id"])
    op.create_foreign_key("agent_run_chat_session_id_fkey", "agent_run", "chat_session", ["chat_session_id"], ["id"])
