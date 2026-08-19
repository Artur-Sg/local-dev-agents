from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
import json

from core.db import insert_event_record
from core.run_repository import get_events_path


@dataclass(frozen=True)
class AgentEvent:
    role: str
    type: str
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    status: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class TeamMessage:
    role: str
    author: str
    text: str
    task_id: str | None = None
    status: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


class Reporter(Protocol):
    def publish(self, message: TeamMessage) -> None: ...


class Narrator(Protocol):
    def narrate(self, event: AgentEvent) -> TeamMessage | None: ...


_reporters: list[Reporter] = []
_narrator: Narrator | None = None


def register_reporter(reporter: Reporter) -> None:
    _reporters.append(reporter)


def get_reporters() -> list[Reporter]:
    return list(_reporters)


def clear_reporters() -> None:
    _reporters.clear()


def set_narrator(narrator: Narrator) -> None:
    global _narrator
    _narrator = narrator


def get_narrator() -> Narrator:
    global _narrator

    if _narrator is None:
        from core.narrator import TeamNarrator

        _narrator = TeamNarrator()

    return _narrator


def emit_event(event: AgentEvent) -> None:
    if event.task_id:
        events_path = get_events_path(event.task_id)
        events_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "role": event.role,
            "type": event.type,
            "message": event.message,
            "payload": event.payload,
            "task_id": event.task_id,
            "status": event.status,
            "created_at": event.created_at.isoformat(),
        }
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        insert_event_record(
            {
                "run_id": event.task_id,
                "role": event.role,
                "type": event.type,
                "message": event.message,
                "payload_json": json.dumps(event.payload, ensure_ascii=False),
                "status": event.status or "",
                "created_at": event.created_at.isoformat(),
            }
        )

    if not _reporters:
        return

    message = get_narrator().narrate(event)
    if message is None:
        return

    for reporter in _reporters:
        reporter.publish(message)
