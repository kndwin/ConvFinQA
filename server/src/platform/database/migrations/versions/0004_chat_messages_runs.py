"""Persist chat transcripts and agent run idempotency records."""
from alembic import op
import sqlalchemy as sa

revision = "0004_chat_messages_runs"
down_revision = "0003_dataset_conversation_rename"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("chat_session", sa.Column("title", sa.String(), nullable=True))
    op.add_column("chat_session", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE chat_session SET updated_at = created_at")
    op.alter_column("chat_session", "updated_at", nullable=False)
    op.create_table(
        "chat_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_session_id", sa.Integer(), sa.ForeignKey("chat_session.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("client_message_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_message_chat_session_id", "chat_message", ["chat_session_id"])
    op.create_index("ix_chat_message_role", "chat_message", ["role"])
    op.create_index("ix_chat_message_client_message_id", "chat_message", ["client_message_id"])
    op.create_table(
        "agent_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False, unique=True),
        sa.Column("chat_session_id", sa.Integer(), sa.ForeignKey("chat_session.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), sa.ForeignKey("chat_message.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_run_run_id", "agent_run", ["run_id"])
    op.create_index("ix_agent_run_chat_session_id", "agent_run", ["chat_session_id"])
    op.create_index("ix_agent_run_status", "agent_run", ["status"])

def downgrade() -> None:
    op.drop_table("agent_run")
    op.drop_table("chat_message")
    op.drop_column("chat_session", "updated_at")
    op.drop_column("chat_session", "title")
