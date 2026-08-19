import sys
import json

from adapters.git import main as git_main
from core.db import list_event_records
from core.run_store import (
    find_latest_resumable_run,
    find_run,
    get_run_current_subtask,
    get_run_events_path,
    list_runs,
)
from core.task_store import list_tasks, recover_tasks_from_files


def _print_task_group(title: str, items) -> None:
    print(title)
    if not items:
        print("  - empty")
        return

    for metadata in items:
        parts = [metadata["task_id"], metadata["title"]]

        if metadata["priority"]:
            parts.append(f"priority={metadata['priority']}")
        if metadata["project"]:
            parts.append(f"project={metadata['project']}")
        if metadata["status"]:
            parts.append(f"status={metadata['status']}")
        if metadata["owner"]:
            parts.append(f"owner={metadata['owner']}")
        if metadata["attempts"]:
            parts.append(f"attempts={metadata['attempts']}")
        if metadata["blocked_by"]:
            parts.append(f"blocked_by={metadata['blocked_by']}")
        if metadata["needs_human_reason"]:
            parts.append(f"reason={metadata['needs_human_reason']}")

        print(f"  - {' | '.join(parts)}")


def _print_runs() -> None:
    print("Runs")
    sessions = list_runs()
    if not sessions:
        print("  - empty")
        return

    for session in sessions:
        current_subtask = get_run_current_subtask(session)
        parts = [session.run_id, f"status={session.status}"]

        if session.task_file:
            parts.append(f"task={session.task_file}")
        parts.append(f"attempts={session.attempt_count}/{session.max_attempts}")
        if current_subtask is not None:
            parts.append(f"subtask={current_subtask.id}:{current_subtask.title}")
        if session.human_summary:
            parts.append(f"human={session.human_summary}")

        print(f"  - {' | '.join(parts)}")


def show_backlog() -> None:
    _print_task_group("Inbox", list_tasks("inbox"))
    _print_task_group("Blocked", list_tasks("blocked"))
    _print_task_group("Needs Human", list_tasks("needs-human"))
    _print_runs()


def recover_backlog() -> None:
    recover_tasks_from_files()
    print("Recovered task records from tasks/* mirror.")


def _tail_events(run_id: str, limit: int = 10) -> list[dict]:
    events = list_event_records(run_id, limit)
    if events:
        return events

    events_path = get_run_events_path(run_id)
    if not events_path.exists():
        return []

    lines = events_path.read_text(encoding="utf-8").splitlines()
    fallback_events: list[dict] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        fallback_events.append(json.loads(line))
    return fallback_events


def _print_run_details(run_id: str) -> int:
    session = find_run(run_id)
    if session is None:
        print(f"Run not found: {run_id}")
        return 1

    current_subtask = get_run_current_subtask(session)
    print(f"Run: {session.run_id}")
    print(f"Status: {session.status}")
    print(f"Task: {session.task_file or '-'}")
    print(f"Attempts: {session.attempt_count}/{session.max_attempts}")
    print(f"Next capability: {session.next_capability}")
    print(f"Plan summary: {session.plan_summary or '-'}")
    print(f"Human summary: {session.human_summary or '-'}")
    print(f"Current subtask: {current_subtask.id + ':' + current_subtask.title if current_subtask else '-'}")
    print("Subtasks")
    if not session.subtasks:
        print("  - empty")
    else:
        for subtask in session.subtasks:
            parts = [subtask.id, subtask.title, f"status={subtask.status}", f"attempts={subtask.attempts}"]
            if subtask.description:
                parts.append(f"description={subtask.description}")
            print(f"  - {' | '.join(parts)}")
            if subtask.acceptance_criteria:
                for criterion in subtask.acceptance_criteria:
                    print(f"    acceptance: {criterion}")

    print("Artifacts")
    if not session.artifacts:
        print("  - empty")
    else:
        for key, value in session.artifacts.items():
            print(f"  - {key}: {value}")

    print("Recent Events")
    events = _tail_events(session.run_id)
    if not events:
        print("  - empty")
    else:
        for event in events:
            status = event.get("status", "")
            role = event.get("role", "")
            event_type = event.get("type", "")
            payload = event.get("payload", {})
            payload_summary = ""
            if payload:
                payload_summary = f" | payload={json.dumps(payload, ensure_ascii=False)}"
            print(f"  - {event.get('created_at', '')} | {role} | {event_type} | {status}{payload_summary}")

    return 0


def show_run(run_id: str | None) -> int:
    target_run_id = run_id
    if target_run_id in {None, "latest"}:
        session = find_latest_resumable_run()
        if session is None:
            sessions = list_runs()
            if not sessions:
                print("No runs found.")
                return 0
            target_run_id = sessions[0].run_id
        else:
            target_run_id = session.run_id

    return _print_run_details(target_run_id)


def main() -> None:
    match sys.argv[1:]:
        case ["backlog"]:
            show_backlog()
        case ["recover"]:
            recover_backlog()
        case ["run"]:
            raise SystemExit(show_run("latest"))
        case ["run", run_id]:
            raise SystemExit(show_run(run_id))
        case _:
            git_main()


if __name__ == "__main__":
    main()
