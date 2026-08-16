"""Add generic multi-chat playground groups."""

from alembic import op
import sqlalchemy as sa

revision = "0013_chat_session_groups"
down_revision = "0012_chat_session_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_session_group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_conversation_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_conversation_id"], ["dataset_conversation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_session_group_dataset_conversation_id", "chat_session_group", ["dataset_conversation_id"])
    op.create_table(
        "chat_session_to_group",
        sa.Column("chat_session_group_id", sa.Integer(), nullable=False),
        sa.Column("chat_session_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chat_session_group_id"], ["chat_session_group.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_session_group_id", "chat_session_id"),
        sa.UniqueConstraint("chat_session_id"),
        sa.UniqueConstraint("chat_session_group_id", "position"),
        sa.CheckConstraint("position >= 0", name="ck_chat_session_to_group_position_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("chat_session_to_group")
    op.drop_index("ix_chat_session_group_dataset_conversation_id", table_name="chat_session_group")
    op.drop_table("chat_session_group")
