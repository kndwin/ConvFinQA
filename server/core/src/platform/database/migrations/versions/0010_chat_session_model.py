"""Add the selected OpenAI model to chat sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0010_chat_session_model"
down_revision = "0009_chat_session_agent_variant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_session",
        # Keep the DB default for newly inserted rows, while allowing the
        # existing rows to be explicitly migrated to the legacy model.
        sa.Column("model", sa.String(), nullable=True, server_default="gpt-5.6-luna"),
    )
    op.execute("UPDATE chat_session SET model = 'gpt-5-mini'")
    op.alter_column("chat_session", "model", nullable=False)


def downgrade() -> None:
    op.drop_column("chat_session", "model")
