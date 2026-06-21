from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_CURRENT_ROLE: ContextVar[str | None] = ContextVar("current_role", default=None)


def get_current_role() -> str:
    role = _CURRENT_ROLE.get()

    if role is None:
        raise RuntimeError("No active role in execution context")

    return role


@contextmanager
def use_role(role: str) -> Iterator[None]:
    token = _CURRENT_ROLE.set(role)

    try:
        yield
    finally:
        _CURRENT_ROLE.reset(token)
