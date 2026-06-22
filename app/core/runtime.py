from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_CURRENT_ROLE: ContextVar[str | None] = ContextVar("current_role", default=None)
_CURRENT_CAPABILITY: ContextVar[str | None] = ContextVar("current_capability", default=None)


def get_current_role() -> str:
    role = _CURRENT_ROLE.get()

    if role is None:
        raise RuntimeError("No active role in execution context")

    return role


def get_current_capability() -> str | None:
    return _CURRENT_CAPABILITY.get()


@contextmanager
def use_role(role: str, capability: str | None = None) -> Iterator[None]:
    role_token = _CURRENT_ROLE.set(role)
    capability_token = _CURRENT_CAPABILITY.set(capability)

    try:
        yield
    finally:
        _CURRENT_CAPABILITY.reset(capability_token)
        _CURRENT_ROLE.reset(role_token)
