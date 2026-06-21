from dataclasses import dataclass, field
from contextvars import ContextVar
from typing import Any, Callable

from runtime import use_role

_TRACE: ContextVar[list[dict[str, str]]] = ContextVar("workflow_trace", default=[])


@dataclass(frozen=True)
class Step:
    name: str
    action: str
    role: str
    func: Callable[..., Any]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


def run_as(role: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    with use_role(role):
        return func(*args, **kwargs)


def run_step(step: Step) -> Any:
    trace = list(_TRACE.get())
    trace.append(
        {
            "name": step.name,
            "action": step.action,
            "role": step.role,
        }
    )
    _TRACE.set(trace)
    return run_as(step.role, step.func, *step.args, **step.kwargs)


def get_trace() -> list[dict[str, str]]:
    return list(_TRACE.get())


def clear_trace() -> None:
    _TRACE.set([])
