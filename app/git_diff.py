import subprocess

from settings import get_sandbox_dir

SANDBOX_DIR = get_sandbox_dir()


def get_git_diff() -> str:
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
    print(get_git_diff())


if __name__ == "__main__":
    main()
