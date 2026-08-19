from pathlib import Path

from core.db import delete_task_record, get_task_record, list_task_records, update_run_task_file, upsert_task_record
from core.run_repository import sync_run_sessions_to_db
from task_files import (
    get_task_path,
    get_task_relpath,
    list_blocked_tasks,
    list_inbox_tasks,
    list_needs_human_tasks,
    mirror_task_file,
    parse_task_front_matter,
    write_task_record_file,
)


GROUP_TO_STATUSES = {
    "inbox": {"todo", "in_progress"},
    "blocked": {"blocked"},
    "needs-human": {"needs_human"},
    "done": {"done"},
}


def list_task_records_in_group(group: str) -> list[dict[str, str]]:
    try:
        allowed_statuses = GROUP_TO_STATUSES[group]
    except KeyError as exc:
        raise ValueError(f"Unsupported task group: {group}")
    return [item for item in list_task_records() if str(item.get("status", "")) in allowed_statuses]


def get_task_record_by_relpath(task_file: str) -> dict[str, str] | None:
    record = get_task_record(task_file)
    if record is None:
        return None
    return {key: str(value) for key, value in record.items()}


def update_task_record_fields(task_file: str, updates: dict[str, str]) -> dict[str, str]:
    record = get_task_record(task_file)
    if record is None:
        raise FileNotFoundError(f"Task record not found: {task_file}")

    updated = dict(record)
    for key, value in updates.items():
        if key in {"attempts", "max_attempts"}:
            updated[key] = int(value or "0")
        else:
            updated[key] = value

    upsert_task_record(updated)
    return {key: str(value) for key, value in updated.items()}


def sync_task_record_to_file(task_file: str, run_id: str = "") -> str:
    record = get_task_record(task_file)
    if record is None:
        raise FileNotFoundError(f"Task record not found: {task_file}")

    source_path = get_task_path(task_file)
    write_task_record_file(source_path, {key: str(value) for key, value in record.items()})

    mirrored, old_relpath = mirror_task_file(source_path, str(record["status"]), run_id)
    mirrored_relpath = get_task_relpath(mirrored)

    if old_relpath and old_relpath != mirrored_relpath:
        updated = dict(record)
        updated["task_file"] = mirrored_relpath
        upsert_task_record(updated)
        delete_task_record(old_relpath)

    return mirrored_relpath


def sync_all_task_paths() -> None:
    for path in list_inbox_tasks() + list_blocked_tasks() + list_needs_human_tasks():
        sync_task_path(path)
    reconcile_run_task_links()


def reconcile_run_task_links() -> None:
    sync_run_sessions_to_db()
    for record in list_task_records():
        run_id = str(record.get("last_run_id", "")).strip()
        task_file = str(record.get("task_file", "")).strip()
        if not run_id or not task_file:
            continue
        update_run_task_file(run_id, task_file)


def sync_task_path(path: Path) -> None:
    metadata, body = parse_task_front_matter(path.read_text(encoding="utf-8"))
    record = {
        "task_file": get_task_relpath(path),
        "task_id": metadata.get("task_id", "").strip() or path.stem,
        "title": metadata.get("title", "").strip() or path.stem,
        "priority": metadata.get("priority", "normal").strip() or "normal",
        "project": metadata.get("project", "").strip(),
        "kind": metadata.get("kind", "").strip(),
        "status": metadata.get("status", "todo").strip() or "todo",
        "owner": metadata.get("owner", "").strip(),
        "attempts": int(metadata.get("attempts", "0") or "0"),
        "max_attempts": int(metadata.get("max_attempts", "0") or "0"),
        "blocked_by": metadata.get("blocked_by", "").strip(),
        "needs_human_reason": metadata.get("needs_human_reason", "").strip(),
        "last_run_id": metadata.get("last_run_id", "").strip(),
        "body_text": body.strip(),
    }
    upsert_task_record(record)


def delete_task_path(relpath: str) -> None:
    delete_task_record(relpath)
