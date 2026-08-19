from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.observability import Observability


class BaseRepository:
    def __init__(
        self,
        session: AsyncSession,
        observability: Observability,
    ) -> None:
        self.session = session
        self.observability = observability
