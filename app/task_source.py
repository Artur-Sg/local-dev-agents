from pathlib import Path

from core.actions import READ_TASK
from core.roles import require_action

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"


def read_current_task() -> str:
    require_action(READ_TASK)
    return TASK_PATH.read_text(encoding="utf-8")
