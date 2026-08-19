from agents.project_lead import parse_task_selection, select_next_task
from core.actions import CALL_MODEL, READ_TASK
from core.capabilities import PREPARE_TASK, SELECT_NEXT_TASK_QUEUE
from core.events import AgentEvent, emit_event
from core.run_store import create_run, find_latest_resumable_run, save_run
from core.task_store import (
    get_blockers,
    list_tasks,
    mark_in_progress,
    move_to_blocked,
    move_to_done,
    move_to_inbox,
    move_to_needs_human,
    read_task_text,
)
from core.state_machine import run_until_terminal
from core.workflow import Step, clear_trace, run_step
from env import get_agent_max_attempts
from reporters.console import setup_console_reporting


def _get_active_task_ids() -> set[str]:
    records = (
        list_tasks("inbox")
        + list_tasks("blocked")
        + list_tasks("needs-human")
    )
    return {str(record["task_id"]) for record in records}


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

    for record in list_tasks("blocked"):
        blockers = get_blockers(record)
        if not blockers:
            continue

        task_id = str(record["task_id"])
        remaining_blockers = [
            blocker for blocker in blockers
            if blocker != task_id and blocker in active_ids
        ]
        if remaining_blockers:
            continue

        moved.append(move_to_inbox(record))

    return moved


def _build_task_candidates() -> tuple[list[dict[str, str]], list[str]]:
    candidates: list[dict[str, str]] = []
    blocked: list[str] = []
    active_task_ids = _get_active_task_ids()

    for metadata in list_tasks("inbox"):
        relpath = str(metadata["task_file"])
        task_id = str(metadata["task_id"])
        blockers = get_blockers(metadata)
        max_attempts = int(str(metadata.get("max_attempts", "0")) or "0")
        attempts = int(str(metadata.get("attempts", "0")) or "0")

        if _is_blocked_by_dependencies(task_id, blockers, active_task_ids):
            blocked.append(relpath)
            continue

        if max_attempts > 0 and attempts >= max_attempts:
            blocked.append(relpath)
            continue

        preview = read_task_text(relpath).strip().splitlines()
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

        session = find_latest_resumable_run()
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

            task_text = run_step(
                Step(
                    name="read_inbox_task",
                    action=READ_TASK,
                    role="orchestrator",
                    capability=PREPARE_TASK,
                    func=read_task_text,
                    args=(task_file,),
                )
            )
            session = create_run(task_text, get_agent_max_attempts(), task_file=task_file)
            save_run(session)
            mark_in_progress({"task_file": task_file}, session.run_id)
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
            archived = move_to_done(session.task_file, session.run_id)
            emit_event(
                AgentEvent(
                    role="orchestrator",
                    type="raw_output",
                    payload={"output": f"Задача архивирована: {archived}."},
                    task_id=session.run_id,
                    status="ok",
                )
            )
            continue

        if session.status in {"blocked", "needs_human"}:
            if session.task_file:
                if session.status == "needs_human":
                    archived = move_to_needs_human(
                        session.task_file,
                        session.run_id,
                        session.human_summary or "Needs human intervention",
                    )
                    emit_event(
                        AgentEvent(
                            role="orchestrator",
                            type="raw_output",
                            payload={"output": f"Задача требует человека: {archived}."},
                            task_id=session.run_id,
                            status="blocked",
                        )
                    )
                else:
                    archived = move_to_blocked(
                        session.task_file,
                        session.run_id,
                        session.human_summary or "Run blocked",
                    )
                    emit_event(
                        AgentEvent(
                            role="orchestrator",
                            type="raw_output",
                            payload={"output": f"Задача заблокирована: {archived}."},
                            task_id=session.run_id,
                            status="blocked",
                        )
                    )
            continue


if __name__ == "__main__":
    main()
