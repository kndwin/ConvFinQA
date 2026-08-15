# Database migrations

Migration files under `src/platform/database/migrations` are schema history,
not application code. Keep revisions deterministic, review destructive changes
carefully, and provide a reversible `downgrade` where practical.

Migration scripts may import Alembic and SQLAlchemy directly. They must not
import module application layers or acquire runtime request dependencies.
