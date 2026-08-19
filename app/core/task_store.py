from pathlib import Path

from core.db import update_run_task_file
from task_files import (
    get_task_path,
    get_task_relpath,
    read_task_file,
    split_csv,
)
from task_repository import (
    get_task_record_by_relpath,
    list_task_records_in_group,
    sync_task_path,
    sync_all_task_paths,
    sync_task_record_to_file,
    update_task_record_fields,
)


def recover_tasks_from_files() -> None:
    sync_all_task_paths()


def list_tasks(group: str) -> list[dict[str, str]]:
    return list_task_records_in_group(group)


def sync_task(task_path: Path) -> None:
    sync_task_path(task_path)


def read_task_text(task_file: str) -> str:
    record = get_task_record_by_relpath(task_file)
    if record is not None:
        body_text = record.get("body_text", "").strip()
        if body_text:
            return body_text

    return read_task_file(get_task_path(task_file))


def get_task_path_from_record(task_record: dict[str, str]) -> Path:
    return get_task_path(str(task_record["task_file"]))


def get_task_relpath_from_path(path: Path) -> str:
    return get_task_relpath(path)


def get_blockers(task_record: dict[str, str]) -> list[str]:
    return split_csv(str(task_record.get("blocked_by", "")))


def transition_task(
    path: Path,
    status: str,
    *,
    run_id: str = "",
    owner: str | None = None,
    reason: str = "",
) -> Path:
    task_file = get_task_relpath(path)
    updates: dict[str, str] = {"status": status}

    if owner is not None:
        updates["owner"] = owner

    if run_id:
        updates["last_run_id"] = run_id

    if status in {"needs_human", "blocked"}:
        updates["needs_human_reason"] = reason.strip()
    else:
        updates["needs_human_reason"] = ""

    update_task_record_fields(task_file, updates)
    mirrored_relpath = sync_task_record_to_file(task_file, run_id)
    if run_id:
        update_run_task_file(run_id, mirrored_relpath)
    return get_task_path(mirrored_relpath)


def mark_task_in_progress(path: Path, run_id: str, owner: str = "project_lead") -> None:
    task_file = get_task_relpath(path)
    record = get_task_record_by_relpath(task_file)
    attempts = int((record or {}).get("attempts", "0") or "0") + 1
    updates = {
        "status": "in_progress",
        "owner": owner,
        "attempts": str(attempts),
        "last_run_id": run_id,
        "needs_human_reason": "",
    }
    update_task_record_fields(task_file, updates)
    mirrored_relpath = sync_task_record_to_file(task_file, run_id)
    update_run_task_file(run_id, mirrored_relpath)


def move_task_to_done(path: Path, run_id: str) -> Path:
    return transition_task(path, "done", run_id=run_id, owner="")


def move_task_to_blocked(path: Path, run_id: str, reason: str) -> Path:
    return transition_task(path, "blocked", run_id=run_id, owner="project_lead", reason=reason)


def move_task_to_needs_human(path: Path, run_id: str, reason: str) -> Path:
    return transition_task(path, "needs_human", run_id=run_id, owner="human", reason=reason)


def move_task_to_inbox(path: Path) -> Path:
    return transition_task(path, "todo", owner="", reason="")


def mark_in_progress(task_record: dict[str, str], run_id: str, owner: str = "project_lead") -> None:
    mark_task_in_progress(get_task_path_from_record(task_record), run_id, owner=owner)


def move_to_inbox(task_record: dict[str, str]) -> str:
    path = move_task_to_inbox(get_task_path_from_record(task_record))
    return get_task_relpath(path)


def move_to_done(task_file: str, run_id: str) -> str:
    path = move_task_to_done(get_task_path(task_file), run_id)
    return get_task_relpath(path)


def move_to_blocked(task_file: str, run_id: str, reason: str) -> str:
    path = move_task_to_blocked(get_task_path(task_file), run_id, reason)
    return get_task_relpath(path)


def move_to_needs_human(task_file: str, run_id: str, reason: str) -> str:
    path = move_task_to_needs_human(get_task_path(task_file), run_id, reason)
    return get_task_relpath(path)
