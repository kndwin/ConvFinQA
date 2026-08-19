from typing import cast

from .contracts import Observability
from .noop import NOOP_OBSERVABILITY

_provider: Observability = cast(Observability, NOOP_OBSERVABILITY)


def get_observability() -> Observability:
    return _provider


def set_observability(observability: Observability) -> None:
    global _provider
    _provider = observability
