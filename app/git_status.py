import subprocess

from roles import require_action
from settings import get_sandbox_dir
from workflow import run_as

SANDBOX_DIR = get_sandbox_dir()


def has_uncommitted_changes() -> bool:
    require_action("read_status")

    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=SANDBOX_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return bool(proc.stdout.strip())


def main() -> None:
    dirty = run_as("manager", has_uncommitted_changes)

    if dirty:
        print("DIRTY")
        raise SystemExit(1)

    print("CLEAN")


if __name__ == "__main__":
    main()
