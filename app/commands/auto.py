from agents.project_lead import parse_task_selection, select_next_task
from core.actions import CALL_MODEL, READ_TASK
from core.capabilities import PREPARE_TASK, SELECT_NEXT_TASK_QUEUE
from core.events import AgentEvent, emit_event
from core.session import create_session, find_latest_resumable_session, save_session
from core.state_machine import run_until_terminal
from core.workflow import Step, clear_trace, run_step
from env import get_agent_max_attempts
from reporters.console import setup_console_reporting
from task_source import (
    get_task_blockers,
    get_task_id,
    get_task_path,
    get_task_relpath,
    list_blocked_tasks,
    list_inbox_tasks,
    list_needs_human_tasks,
    mark_task_in_progress,
    move_task_to_blocked,
    move_task_to_done,
    move_task_to_inbox,
    move_task_to_needs_human,
    read_task_file,
    read_task_metadata,
)


def _get_active_task_ids() -> set[str]:
    active_paths = list_inbox_tasks() + list_blocked_tasks() + list_needs_human_tasks()
    return {get_task_id(path) for path in active_paths}


def _is_blocked_by_dependencies(task_id: str, blockers: list[str], active_task_ids: set[str]) -> bool:
    for blocker in blockers:
        if blocker == task_id:
            continue
        if blocker in active_task_ids:
            return True

    return False


def _revive_unblocked_tasks() -> list[str]:
    moved: list[str] = []
    active_ids = _get_active_task_ids()

    for path in list_blocked_tasks():
        task_id = get_task_id(path)
        blockers = get_task_blockers(path)
        remaining_blockers = [
            blocker for blocker in blockers
            if blocker != task_id and blocker in active_ids
        ]
        if remaining_blockers:
            continue

        moved_path = move_task_to_inbox(path)
        moved.append(get_task_relpath(moved_path))

    return moved


def _build_task_candidates() -> tuple[list[dict[str, str]], list[str]]:
    candidates: list[dict[str, str]] = []
    blocked: list[str] = []
    active_task_ids = _get_active_task_ids()

    for path in list_inbox_tasks():
        relpath = get_task_relpath(path)
        metadata = read_task_metadata(path)
        task_id = metadata["task_id"]
        blockers = get_task_blockers(path)
        max_attempts = int(metadata.get("max_attempts", "0") or "0")
        attempts = int(metadata.get("attempts", "0") or "0")

        if _is_blocked_by_dependencies(task_id, blockers, active_task_ids):
            blocked.append(relpath)
            continue

        if max_attempts > 0 and attempts >= max_attempts:
            blocked.append(relpath)
            continue

        preview = path.read_text(encoding="utf-8").strip().splitlines()
        summary = " ".join(line.strip() for line in preview[:4] if line.strip())[:240]
        candidates.append(
            {
                "task_file": relpath,
                "task_id": task_id,
                "title": metadata["title"],
                "priority": metadata["priority"],
                "project": metadata["project"],
                "kind": metadata["kind"],
                "status": metadata["status"],
                "owner": metadata["owner"],
                "attempts": metadata["attempts"],
                "max_attempts": metadata["max_attempts"],
                "blocked_by": metadata["blocked_by"],
                "needs_human_reason": metadata["needs_human_reason"],
                "summary": summary,
            }
        )

    return candidates, blocked


def _select_next_task_file() -> tuple[str | None, str, list[str]]:
    candidates, blocked = _build_task_candidates()
    if not candidates:
        return None, "", blocked

    if len(candidates) == 1:
        return candidates[0]["task_file"], "В очереди осталась одна исполнимая задача.", blocked

    response = run_step(
        Step(
            name="select_next_task_queue",
            action=CALL_MODEL,
            role="orchestrator",
            capability=SELECT_NEXT_TASK_QUEUE,
            func=select_next_task,
            args=(candidates,),
        )
    )
    task_file, reason = parse_task_selection(response)
    known_files = {candidate["task_file"] for candidate in candidates}
    if task_file not in known_files:
        raise ValueError(f"Project lead selected unknown task file: {task_file}")
    return task_file, reason, blocked


def main() -> None:
    setup_console_reporting()
    clear_trace()

    while True:
        revived = _revive_unblocked_tasks()
        for relpath in revived:
            emit_event(
                AgentEvent(
                    role="orchestrator",
                    type="raw_output",
                    payload={"output": f"Задача снова доступна для очереди: {relpath}."},
                    status="ok",
                )
            )

        session = find_latest_resumable_session()
        if session is None:
            task_file, reason, blocked = _select_next_task_file()
            if task_file is None:
                if blocked:
                    emit_event(
                        AgentEvent(
                            role="orchestrator",
                            type="raw_output",
                            payload={
                                "output": "Автоматическая очередь остановлена: остались только задачи, ожидающие человека."
                            },
                            status="blocked",
                        )
                    )
                    raise SystemExit(1)

                emit_event(
                    AgentEvent(
                        role="orchestrator",
                        type="raw_output",
                        payload={"output": "Очередь задач пуста."},
                        status="ok",
                    )
                )
                raise SystemExit(0)

            task_path = get_task_path(task_file)
            task_text = run_step(
                Step(
                    name="read_inbox_task",
                    action=READ_TASK,
                    role="orchestrator",
                    capability=PREPARE_TASK,
                    func=read_task_file,
                    args=(task_path,),
                )
            )
            session = create_session(task_text, get_agent_max_attempts(), task_file=task_file)
            save_session(session)
            mark_task_in_progress(task_path, session.run_id)
            emit_event(
                AgentEvent(
                    role="orchestrator",
                    type="raw_output",
                    payload={"output": f"Создан новый run {session.run_id} для {task_file}. {reason}"},
                    task_id=session.run_id,
                    status="started",
                )
            )
        else:
            emit_event(
                AgentEvent(
                    role="orchestrator",
                    type="raw_output",
                    payload={"output": f"Продолжаю run {session.run_id} со статуса {session.status}."},
                    task_id=session.run_id,
                    status="resumed",
                )
            )

        session = run_until_terminal(session)
        if session.status == "done" and session.task_file:
            task_path = get_task_path(session.task_file)
            if task_path.exists():
                archived = move_task_to_done(task_path, session.run_id)
                emit_event(
                    AgentEvent(
                        role="orchestrator",
                        type="raw_output",
                        payload={"output": f"Задача архивирована: {get_task_relpath(archived)}."},
                        task_id=session.run_id,
                        status="ok",
                    )
                )
            continue

        if session.status in {"blocked", "needs_human"}:
            if session.task_file:
                task_path = get_task_path(session.task_file)
                if task_path.exists():
                    if session.status == "needs_human":
                        archived = move_task_to_needs_human(
                            task_path,
                            session.run_id,
                            session.human_summary or "Needs human intervention",
                        )
                        emit_event(
                            AgentEvent(
                                role="orchestrator",
                                type="raw_output",
                                payload={"output": f"Задача требует человека: {get_task_relpath(archived)}."},
                                task_id=session.run_id,
                                status="blocked",
                            )
                        )
                    else:
                        archived = move_task_to_blocked(
                            task_path,
                            session.run_id,
                            session.human_summary or "Run blocked",
                        )
                        emit_event(
                            AgentEvent(
                                role="orchestrator",
                                type="raw_output",
                                payload={"output": f"Задача заблокирована: {get_task_relpath(archived)}."},
                                task_id=session.run_id,
                                status="blocked",
                            )
                        )
            continue


if __name__ == "__main__":
    main()
