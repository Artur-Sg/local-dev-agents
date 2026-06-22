from dataclasses import dataclass, field
from contextvars import ContextVar
from typing import Any, Callable

from core.events import AgentEvent, emit_event
from core.roles import require_role_action
from core.runtime import use_role

_TRACE: ContextVar[list[dict[str, str]]] = ContextVar("workflow_trace", default=[])


@dataclass(frozen=True)
class Step:
    name: str
    action: str
    role: str
    func: Callable[..., Any]
    capability: str | None = None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


def run_as(
    role: str,
    func: Callable[..., Any],
    *args: Any,
    capability: str | None = None,
    **kwargs: Any,
) -> Any:
    with use_role(role, capability):
        return func(*args, **kwargs)


def run_step(step: Step) -> Any:
    require_role_action(step.role, step.action, step.capability)
    emit_event(
        AgentEvent(
            role=step.role,
            type="step_started",
            payload={
                "step_name": step.name,
                "action": step.action,
                "capability": step.capability,
            },
            status="started",
        )
    )

    trace = list(_TRACE.get())
    trace.append(
        {
            "name": step.name,
            "action": step.action,
            "role": step.role,
            "capability": step.capability or "",
        }
    )
    _TRACE.set(trace)

    try:
        result = run_as(
            step.role,
            step.func,
            *step.args,
            capability=step.capability,
            **step.kwargs,
        )
    except Exception as exc:
        emit_event(
            AgentEvent(
                role=step.role,
                type="step_failed",
                payload={
                    "step_name": step.name,
                    "action": step.action,
                    "capability": step.capability,
                    "error": str(exc),
                },
                status="failed",
            )
        )
        raise

    emit_event(
        AgentEvent(
            role=step.role,
            type="step_succeeded",
            payload={
                "step_name": step.name,
                "action": step.action,
                "capability": step.capability,
            },
            status="ok",
        )
    )
    return result


def get_trace() -> list[dict[str, str]]:
    return list(_TRACE.get())


def clear_trace() -> None:
    _TRACE.set([])
