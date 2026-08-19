from core.run_models import RunSession, get_current_subtask
from core.run_repository import (
    create_session,
    find_latest_resumable_session,
    find_session,
    get_events_path,
    list_sessions,
    save_session,
)


def create_run(task_text: str, max_attempts: int, task_file: str = "") -> RunSession:
    return create_session(task_text, max_attempts, task_file=task_file)


def save_run(session: RunSession) -> None:
    save_session(session)


def find_latest_resumable_run() -> RunSession | None:
    return find_latest_resumable_session()


def find_run(run_id: str) -> RunSession | None:
    return find_session(run_id)


def list_runs() -> list[RunSession]:
    return list_sessions()


def get_run_events_path(run_id: str):
    return get_events_path(run_id)


def get_run_current_subtask(session: RunSession):
    return get_current_subtask(session)
