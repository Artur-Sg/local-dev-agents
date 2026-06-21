import subprocess

from settings import get_sandbox_dir

SANDBOX_DIR = get_sandbox_dir()


def has_uncommitted_changes() -> bool:
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
    if has_uncommitted_changes():
        print("DIRTY")
        raise SystemExit(1)

    print("CLEAN")


if __name__ == "__main__":
    main()
