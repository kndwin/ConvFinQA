"""Add reusable tags for chat sessions."""

from alembic import op
import sqlalchemy as sa


revision = "0012_chat_session_tags"
down_revision = "0011_chat_session_approach_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_session_tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("value"),
    )
    op.create_index("ix_chat_session_tag_value", "chat_session_tag", ["value"], unique=False)
    op.create_table(
        "chat_session_to_tag",
        sa.Column("chat_session_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["chat_session_tag.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_session_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("chat_session_to_tag")
    op.drop_index("ix_chat_session_tag_value", table_name="chat_session_tag")
    op.drop_table("chat_session_tag")
