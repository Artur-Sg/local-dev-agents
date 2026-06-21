import subprocess

from roles import require_action
from settings import get_sandbox_dir
from workflow import run_as

SANDBOX_DIR = get_sandbox_dir()


def get_git_diff() -> str:
    require_action("read_diff")

    proc = subprocess.run(
        ["git", "diff", "--", "."],
        cwd=SANDBOX_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return proc.stdout


def main() -> None:
    print(run_as("manager", get_git_diff))


if __name__ == "__main__":
    main()
