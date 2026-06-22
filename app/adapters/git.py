import subprocess
import sys

from core.actions import READ_CHANGES, READ_DIFF, READ_STATUS
from core.capabilities import INSPECT_CHANGES, PREPARE_TASK
from core.events import AgentEvent, emit_event
from core.roles import require_action
from core.settings import get_sandbox_dir
from core.workflow import Step, run_step
from reporters.console import setup_console_reporting

SANDBOX_DIR = get_sandbox_dir()


def _git_diff() -> str:
    proc = subprocess.run(
        ["git", "diff", "--", "."],
        cwd=SANDBOX_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return proc.stdout


def _git_status_porcelain() -> str:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=SANDBOX_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return proc.stdout


def get_git_diff() -> str:
    require_action(READ_DIFF)
    return _git_diff()


def get_git_status_porcelain() -> str:
    require_action(READ_STATUS)
    return _git_status_porcelain()


def get_git_review_text() -> str:
    require_action(READ_CHANGES)

    status = _git_status_porcelain()
    diff = _git_diff()

    if not status.strip() and not diff.strip():
        return ""

    parts = []

    if status.strip():
        parts.append("Git status:\n" + status)

    if diff.strip():
        parts.append("Git diff:\n" + diff)

    return "\n\n".join(parts)


def has_uncommitted_changes() -> bool:
    return bool(_git_status_porcelain().strip())


def main() -> None:
    setup_console_reporting()
    match sys.argv[1:]:
        case ["diff"]:
            changes = run_step(
                Step(
                    name="show_git_changes",
                    action=READ_CHANGES,
                    role="orchestrator",
                    capability=INSPECT_CHANGES,
                    func=get_git_review_text,
                )
            )
            emit_event(
                AgentEvent(
                    role="orchestrator",
                    type="git_changes",
                    payload={"changes": changes},
                )
            )
        case ["status"]:
            dirty = run_step(
                Step(
                    name="show_git_status",
                    action=READ_STATUS,
                    role="orchestrator",
                    capability=PREPARE_TASK,
                    func=has_uncommitted_changes,
                )
            )
            if dirty:
                emit_event(AgentEvent(role="orchestrator", type="git_status_dirty", status="dirty"))
                raise SystemExit(1)
            emit_event(AgentEvent(role="orchestrator", type="git_status_clean", status="clean"))
        case _:
            raise SystemExit("Usage: python3 app/adapters/git.py [diff|status]")

if __name__ == "__main__":
    main()
