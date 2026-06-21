import subprocess

from settings import get_sandbox_dir

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


def main() -> None:
    run(["git", "restore", "."])
    run(["git", "clean", "-fd"])
    print("Rejected agent changes. Working tree restored.")


if __name__ == "__main__":
    main()
