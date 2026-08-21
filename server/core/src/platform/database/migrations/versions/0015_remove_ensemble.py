"""Remove ensemble sessions and their configuration data.

This cleanup is irreversible: downgrade restores only the nullable column,
not the deleted sessions, groups, messages, runs, or links.
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_remove_ensemble"
down_revision = "0014_ensemble_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Removing the group first leaves its non-ensemble sessions ungrouped.
    op.execute(
        sa.text(
            """
            DELETE FROM chat_session_group
            WHERE id IN (
                SELECT link.chat_session_group_id
                FROM chat_session_to_group AS link
                JOIN chat_session AS session ON session.id = link.chat_session_id
                WHERE session.agent_approach = 'ensemble'
            )
            """
        )
    )
    # CASCADE removes messages, runs, tags, and any remaining link rows.
    op.execute(sa.text("DELETE FROM chat_session WHERE agent_approach = 'ensemble'"))
    op.drop_column("chat_session", "ensemble_config_json")


def downgrade() -> None:
    # Deleted data cannot be restored by this downgrade.
    op.add_column("chat_session", sa.Column("ensemble_config_json", sa.Text(), nullable=True))
