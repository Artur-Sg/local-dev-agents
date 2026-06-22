import subprocess

from adapters.git import has_uncommitted_changes
from core.actions import APPROVE_CHANGES, COMMIT_CHANGES, READ_DIFF, READ_STATUS, REJECT_CHANGES, RESTORE_CHANGES
from core.roles import require_action
from core.settings import get_project_dir

PROJECT_DIR = get_project_dir()


def run_git_command(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)
    return proc.stdout


def verify_approval_request() -> None:
    require_action(APPROVE_CHANGES)


def verify_approval_for_diff(diff: str) -> None:
    require_action(APPROVE_CHANGES)
    if not diff.strip():
        raise RuntimeError("No changes to approve.")


def commit_changes() -> str:
    require_action(COMMIT_CHANGES)
    require_action(READ_STATUS)
    require_action(READ_DIFF)

    if not has_uncommitted_changes():
        raise RuntimeError("No changes to commit.")

    run_git_command(["git", "add", "."])
    return run_git_command(["git", "commit", "-m", "Approve agent changes"])


def verify_reject_request() -> None:
    require_action(REJECT_CHANGES)


def restore_changes() -> None:
    require_action(RESTORE_CHANGES)
    run_git_command(["git", "restore", "."])
    run_git_command(["git", "clean", "-fd"])
