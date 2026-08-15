"""Rename conversations to dataset conversations without copying data."""

from alembic import op

revision = "0003_dataset_conversation_rename"
down_revision = "0002_chat_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conversation RENAME TO dataset_conversation")
    op.execute("ALTER TABLE dataset_conversation RENAME CONSTRAINT pk_conversation TO pk_dataset_conversation")
    op.execute("ALTER INDEX ix_conversation_split RENAME TO ix_dataset_conversation_split")
    op.execute("ALTER INDEX ix_conversation_source_id RENAME TO ix_dataset_conversation_source_id")

    op.execute("ALTER TABLE table_cell RENAME COLUMN conversation_id TO dataset_conversation_id")
    op.execute("ALTER TABLE dialogue_turn RENAME COLUMN conversation_id TO dataset_conversation_id")
    op.execute("ALTER TABLE table_cell RENAME CONSTRAINT fk_table_cell_conversation TO fk_table_cell_dataset_conversation")
    op.execute("ALTER TABLE dialogue_turn RENAME CONSTRAINT fk_dialogue_turn_conversation TO fk_dialogue_turn_dataset_conversation")
    op.execute("ALTER TABLE chat_session RENAME CONSTRAINT fk_chat_session_conversation TO fk_chat_session_dataset_conversation")
    op.execute("ALTER INDEX ix_table_cell_conversation_id RENAME TO ix_table_cell_dataset_conversation_id")
    op.execute("ALTER INDEX ix_dialogue_turn_conversation_id RENAME TO ix_dialogue_turn_dataset_conversation_id")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_dialogue_turn_dataset_conversation_id RENAME TO ix_dialogue_turn_conversation_id")
    op.execute("ALTER INDEX ix_table_cell_dataset_conversation_id RENAME TO ix_table_cell_conversation_id")
    op.execute("ALTER TABLE chat_session RENAME CONSTRAINT fk_chat_session_dataset_conversation TO fk_chat_session_conversation")
    op.execute("ALTER TABLE dialogue_turn RENAME CONSTRAINT fk_dialogue_turn_dataset_conversation TO fk_dialogue_turn_conversation")
    op.execute("ALTER TABLE table_cell RENAME CONSTRAINT fk_table_cell_dataset_conversation TO fk_table_cell_conversation")
    op.execute("ALTER TABLE dialogue_turn RENAME COLUMN dataset_conversation_id TO conversation_id")
    op.execute("ALTER TABLE table_cell RENAME COLUMN dataset_conversation_id TO conversation_id")
    op.execute("ALTER INDEX ix_dataset_conversation_source_id RENAME TO ix_conversation_source_id")
    op.execute("ALTER INDEX ix_dataset_conversation_split RENAME TO ix_conversation_split")
    op.execute("ALTER TABLE dataset_conversation RENAME CONSTRAINT pk_dataset_conversation TO pk_conversation")
    op.execute("ALTER TABLE dataset_conversation RENAME TO conversation")
