from pathlib import Path

from core.actions import READ_TASK
from core.roles import require_action
from core.settings import ROOT

TASKS_DIR = ROOT / "tasks"
INBOX_DIR = TASKS_DIR / "inbox"
DONE_DIR = TASKS_DIR / "done"
BLOCKED_DIR = TASKS_DIR / "blocked"
NEEDS_HUMAN_DIR = TASKS_DIR / "needs-human"

STATUS_TO_DIR = {
    "todo": INBOX_DIR,
    "in_progress": INBOX_DIR,
    "blocked": BLOCKED_DIR,
    "needs_human": NEEDS_HUMAN_DIR,
    "done": DONE_DIR,
}


def parse_task_front_matter(text: str) -> tuple[dict[str, str], str]:
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


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def serialize_front_matter(metadata: dict[str, str], body: str) -> str:
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


def build_task_file_content(record: dict[str, str]) -> str:
    metadata = {
        "task_id": str(record.get("task_id", "")).strip(),
        "title": str(record.get("title", "")).strip(),
        "priority": str(record.get("priority", "")).strip(),
        "project": str(record.get("project", "")).strip(),
        "kind": str(record.get("kind", "")).strip(),
        "status": str(record.get("status", "")).strip(),
        "attempts": str(record.get("attempts", "")).strip(),
        "max_attempts": str(record.get("max_attempts", "")).strip(),
        "owner": str(record.get("owner", "")).strip(),
        "blocked_by": str(record.get("blocked_by", "")).strip(),
        "needs_human_reason": str(record.get("needs_human_reason", "")).strip(),
        "last_run_id": str(record.get("last_run_id", "")).strip(),
    }
    body = str(record.get("body_text", "")).strip()
    return serialize_front_matter(metadata, body)


def write_task_record_file(path: Path, record: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_task_file_content(record), encoding="utf-8")


def ensure_task_dirs() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)
    NEEDS_HUMAN_DIR.mkdir(parents=True, exist_ok=True)


def list_inbox_tasks() -> list[Path]:
    ensure_task_dirs()
    return sorted(path for path in INBOX_DIR.glob("*.md") if path.is_file())


def list_blocked_tasks() -> list[Path]:
    ensure_task_dirs()
    return sorted(path for path in BLOCKED_DIR.glob("*.md") if path.is_file())


def list_needs_human_tasks() -> list[Path]:
    ensure_task_dirs()
    return sorted(path for path in NEEDS_HUMAN_DIR.glob("*.md") if path.is_file())


def read_task_file(path: Path) -> str:
    require_action(READ_TASK)
    _metadata, body = parse_task_front_matter(path.read_text(encoding="utf-8"))
    return body.strip()


def get_task_relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def get_task_path(relpath: str) -> Path:
    return ROOT / relpath


def get_directory_for_status(status: str) -> Path:
    try:
        return STATUS_TO_DIR[status]
    except KeyError as exc:
        raise ValueError(f"Unsupported task status: {status}") from exc


def mirror_task_file(path: Path, status: str, run_id: str = "") -> tuple[Path, str]:
    target_dir = get_directory_for_status(status)
    target_dir.mkdir(parents=True, exist_ok=True)

    if path.parent == target_dir:
        return path, ""

    target = target_dir / path.name
    if target.exists() and target != path:
        suffix = f"{run_id}__" if run_id else ""
        target = target_dir / f"{suffix}{path.name}"

    old_relpath = get_task_relpath(path)
    renamed = path.rename(target)
    return renamed, old_relpath
