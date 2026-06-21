import subprocess

from roles import require_action
from settings import get_sandbox_dir
from workflow import Step, clear_trace, run_step

SANDBOX_DIR = get_sandbox_dir()


def run(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd,
        cwd=SANDBOX_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)
    return proc.stdout


def reject_changes() -> None:
    require_action("reject_changes")
    run(["git", "restore", "."])
    run(["git", "clean", "-fd"])


def main() -> None:
    clear_trace()
    run_step(
        Step(
            name="reject_request",
            action="reject_changes",
            role="telegram_user",
            func=reject_changes,
        )
    )
    print("Rejected agent changes. Working tree restored.")


if __name__ == "__main__":
    main()
