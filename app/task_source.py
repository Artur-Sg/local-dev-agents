from pathlib import Path

from core.actions import READ_TASK
from core.roles import require_action
from core.settings import get_task_overlay_path

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
INBOX_DIR = TASKS_DIR / "inbox"
DONE_DIR = TASKS_DIR / "done"
BLOCKED_DIR = TASKS_DIR / "blocked"
NEEDS_HUMAN_DIR = TASKS_DIR / "needs-human"
TASK_PATH = ROOT / "tasks" / "task.md"


def _parse_task_front_matter(text: str) -> tuple[dict[str, str], str]:
    stripped = text.strip()
    if not stripped.startswith("---\n"):
        return {}, stripped

    lines = stripped.splitlines()
    if lines[0].strip() != "---":
        return {}, stripped

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, stripped

    metadata: dict[str, str] = {}
    for line in lines[1:end_index]:
        raw = line.strip()
        if not raw or raw.startswith("#") or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            metadata[key] = value

    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _serialize_front_matter(metadata: dict[str, str], body: str) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if value == "":
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    if body.strip():
        lines.append(body.strip())
    return "\n".join(lines).rstrip() + "\n"


def _apply_overlay(base_task: str) -> str:
    overlay_path = get_task_overlay_path()

    if overlay_path is None:
        return base_task

    overlay = overlay_path.read_text(encoding="utf-8").strip()
    return f"{base_task}\n\n{overlay}".strip()


def read_current_task() -> str:
    require_action(READ_TASK)
    base_task = TASK_PATH.read_text(encoding="utf-8").strip()
    return _apply_overlay(base_task)


def list_inbox_tasks() -> list[Path]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)
    NEEDS_HUMAN_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path for path in INBOX_DIR.glob("*.md") if path.is_file())


def list_blocked_tasks() -> list[Path]:
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path for path in BLOCKED_DIR.glob("*.md") if path.is_file())


def list_needs_human_tasks() -> list[Path]:
    NEEDS_HUMAN_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(path for path in NEEDS_HUMAN_DIR.glob("*.md") if path.is_file())


def read_task_file(path: Path) -> str:
    require_action(READ_TASK)
    _metadata, body = _parse_task_front_matter(path.read_text(encoding="utf-8"))
    return _apply_overlay(body.strip())


def read_task_metadata(path: Path) -> dict[str, str]:
    metadata, body = _parse_task_front_matter(path.read_text(encoding="utf-8"))
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    task_id = metadata.get("task_id", "").strip() or path.stem

    result = {
        "task_id": task_id,
        "title": metadata.get("title", first_line[:120] if first_line else path.stem),
        "priority": metadata.get("priority", "normal"),
        "project": metadata.get("project", ""),
        "kind": metadata.get("kind", ""),
        "status": metadata.get("status", "todo"),
        "owner": metadata.get("owner", ""),
        "blocked_by": metadata.get("blocked_by", ""),
        "attempts": metadata.get("attempts", "0"),
        "max_attempts": metadata.get("max_attempts", ""),
        "needs_human_reason": metadata.get("needs_human_reason", ""),
    }
    return result


def get_task_relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def get_task_path(relpath: str) -> Path:
    return ROOT / relpath


def get_task_blockers(path: Path) -> list[str]:
    metadata = read_task_metadata(path)
    return _split_csv(metadata.get("blocked_by", ""))


def get_task_id(path: Path) -> str:
    return read_task_metadata(path)["task_id"]


def update_task_metadata(path: Path, updates: dict[str, str]) -> None:
    raw_text = path.read_text(encoding="utf-8")
    metadata, body = _parse_task_front_matter(raw_text)
    if not metadata.get("task_id", "").strip():
        metadata["task_id"] = path.stem

    base_title = metadata.get("title", "")
    if not base_title:
        first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
        if first_line:
            metadata["title"] = first_line[:120]

    for key, value in updates.items():
        if value == "":
            metadata.pop(key, None)
        else:
            metadata[key] = value

    path.write_text(_serialize_front_matter(metadata, body), encoding="utf-8")


def mark_task_in_progress(path: Path, run_id: str, owner: str = "project_lead") -> None:
    metadata = read_task_metadata(path)
    attempts = int(metadata.get("attempts", "0") or "0") + 1
    update_task_metadata(
        path,
        {
            "status": "in_progress",
            "owner": owner,
            "attempts": str(attempts),
            "last_run_id": run_id,
            "needs_human_reason": "",
        },
    )


def mark_task_needs_human(path: Path, run_id: str, reason: str) -> None:
    update_task_metadata(
        path,
        {
            "status": "needs_human",
            "owner": "human",
            "last_run_id": run_id,
            "needs_human_reason": reason.strip(),
        },
    )


def mark_task_blocked(path: Path, run_id: str, reason: str) -> None:
    update_task_metadata(
        path,
        {
            "status": "blocked",
            "owner": "project_lead",
            "last_run_id": run_id,
            "needs_human_reason": reason.strip(),
        },
    )


def move_task_to_done(path: Path, run_id: str) -> Path:
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    update_task_metadata(
        path,
        {
            "status": "done",
            "owner": "",
            "last_run_id": run_id,
            "needs_human_reason": "",
        },
    )
    target = DONE_DIR / path.name
    if target.exists():
        target = DONE_DIR / f"{run_id}__{path.name}"
    return path.rename(target)


def move_task_to_blocked(path: Path, run_id: str, reason: str) -> Path:
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)
    mark_task_blocked(path, run_id, reason)
    target = BLOCKED_DIR / path.name
    if target.exists():
        target = BLOCKED_DIR / f"{run_id}__{path.name}"
    return path.rename(target)


def move_task_to_needs_human(path: Path, run_id: str, reason: str) -> Path:
    NEEDS_HUMAN_DIR.mkdir(parents=True, exist_ok=True)
    mark_task_needs_human(path, run_id, reason)
    target = NEEDS_HUMAN_DIR / path.name
    if target.exists():
        target = NEEDS_HUMAN_DIR / f"{run_id}__{path.name}"
    return path.rename(target)


def move_task_to_inbox(path: Path) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    update_task_metadata(
        path,
        {
            "status": "todo",
            "owner": "",
            "needs_human_reason": "",
        },
    )
    target = INBOX_DIR / path.name
    if target.exists():
        target = INBOX_DIR / f"{get_task_id(path)}__{path.name}"
    return path.rename(target)
