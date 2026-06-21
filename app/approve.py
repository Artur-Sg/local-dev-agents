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


def verify_approval() -> None:
    require_action("approve_changes")


def commit_changes() -> str:
    require_action("commit_changes")
    require_action("read_diff")
    run(["git", "add", "."])
    return run(["git", "commit", "-m", "Approve agent changes"])


def main() -> None:
    clear_trace()
    run_step(
        Step(
            name="approve_request",
            action="approve_changes",
            role="telegram_user",
            func=verify_approval,
        )
    )
    output = run_step(
        Step(
            name="approve_commit",
            action="commit_changes",
            role="committer",
            func=commit_changes,
        )
    )
    print(output)


if __name__ == "__main__":
    main()
