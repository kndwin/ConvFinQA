"""Create chat sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0002_chat_session"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("dataset_conversation_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_conversation_id"],
            ["conversation.id"],
            name="fk_chat_session_conversation",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_session"),
    )
    op.create_index(
        "ix_chat_session_dataset_conversation_id",
        "chat_session",
        ["dataset_conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_session_dataset_conversation_id", table_name="chat_session")
    op.drop_table("chat_session")
