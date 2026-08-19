"""Link completed runs to their assistant messages."""
from alembic import op

revision = "0006_agent_run_assistant_fk"
down_revision = "0005_chat_message_constraints"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_foreign_key("fk_agent_run_assistant_message_id_chat_message", "agent_run", "chat_message", ["assistant_message_id"], ["id"], ondelete="SET NULL")

def downgrade() -> None:
    op.drop_constraint("fk_agent_run_assistant_message_id_chat_message", "agent_run", type_="foreignkey")
