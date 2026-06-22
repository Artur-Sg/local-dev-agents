from pathlib import Path

from core.actions import READ_TASK
from core.roles import require_action
from core.settings import get_task_overlay_path

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"


def read_current_task() -> str:
    require_action(READ_TASK)
    base_task = TASK_PATH.read_text(encoding="utf-8").strip()
    overlay_path = get_task_overlay_path()

    if overlay_path is None:
        return base_task

    overlay = overlay_path.read_text(encoding="utf-8").strip()
    return f"{base_task}\n\n{overlay}".strip()
