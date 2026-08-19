from src.platform.observability import Observability


class BaseService:
    def __init__(self, observability: Observability) -> None:
        self.observability = observability
