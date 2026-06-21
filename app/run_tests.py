import subprocess

from roles import require_action
from settings import get_sandbox_dir
from workflow import run_as

SANDBOX_DIR = get_sandbox_dir()


def run_tests() -> tuple[int, str]:
    require_action("run_tests")

    proc = subprocess.run(
        ["./run_tests.sh"],
        cwd=SANDBOX_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    return proc.returncode, proc.stdout


def main() -> None:
    code, output = run_as("tester", run_tests)
    print(output)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
