"""Create ConvFinQA tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("split", sa.String(), nullable=False),
        sa.Column("pre_text", sa.String(), nullable=False),
        sa.Column("post_text", sa.String(), nullable=False),
        sa.Column("num_dialogue_turns", sa.Integer()),
        sa.Column("has_type2_question", sa.Boolean()),
        sa.Column("has_duplicate_columns", sa.Boolean()),
        sa.Column("has_non_numeric_values", sa.Boolean()),
        sa.Column("features_json", sa.String(), nullable=False),
        sa.Column("doc_json", sa.String()),
        sa.Column("dialogue_json", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_conversation"),
    )
    op.create_index("ix_conversation_split", "conversation", ["split"])
    op.create_index("ix_conversation_source_id", "conversation", ["source_id"], unique=True)
    op.create_table(
        "table_cell",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("column_heading", sa.String(), nullable=False),
        sa.Column("row_label", sa.String(), nullable=False),
        sa.Column("value_type", sa.String(), nullable=False),
        sa.Column("text_value", sa.String()),
        sa.Column("numeric_value", sa.Float()),
        sa.Column("raw_value", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"], name="fk_table_cell_conversation"),
        sa.PrimaryKeyConstraint("id", name="pk_table_cell"),
    )
    op.create_index("ix_table_cell_conversation_id", "table_cell", ["conversation_id"])
    op.create_index("ix_table_cell_value_type", "table_cell", ["value_type"])
    op.create_table(
        "dialogue_turn",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("question", sa.String()),
        sa.Column("answer_text", sa.String()),
        sa.Column("program", sa.String()),
        sa.Column("executed_answer_json", sa.String()),
        sa.Column("qa_split", sa.Boolean()),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversation.id"], name="fk_dialogue_turn_conversation"),
        sa.PrimaryKeyConstraint("id", name="pk_dialogue_turn"),
    )
    op.create_index("ix_dialogue_turn_conversation_id", "dialogue_turn", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("dialogue_turn")
    op.drop_table("table_cell")
    op.drop_table("conversation")
