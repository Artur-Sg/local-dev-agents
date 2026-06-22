import subprocess
import shlex

from core.actions import RUN_TESTS
from core.capabilities import RUN_TESTS as RUN_TESTS_CAPABILITY
from core.events import AgentEvent, emit_event
from core.roles import require_action
from core.settings import ROOT, get_project_dir, get_test_runner
from core.workflow import Step, run_step
from reporters.console import setup_console_reporting

PROJECT_DIR = get_project_dir()
TEST_RUNNER = get_test_runner()


def run_tests() -> tuple[int, str]:
    require_action(RUN_TESTS)

    setup_commands = TEST_RUNNER["setup_commands"]
    base_command = shlex.join(TEST_RUNNER["command"])
    if setup_commands:
        joined_setup = " && ".join(setup_commands)
        runner_command = ["sh", "-lc", f"{joined_setup} && {base_command}"]
    else:
        runner_command = TEST_RUNNER["command"]

    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        "1g",
        "--cpus",
        "1",
        "--pids-limit",
        "256",
        "--security-opt",
        "no-new-privileges=true",
        "-v",
        f"{PROJECT_DIR}:/workspace",
        "-w",
        "/workspace",
        TEST_RUNNER["image"],
        *runner_command,
    ]

    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    return proc.returncode, proc.stdout


def main() -> None:
    setup_console_reporting()
    code, output = run_step(
        Step(
            name="run_tests_once",
            action=RUN_TESTS,
            role="tester",
            capability=RUN_TESTS_CAPABILITY,
            func=run_tests,
        )
    )
    event_type = "tests_passed" if code == 0 else "tests_failed"
    emit_event(
        AgentEvent(
            role="tester",
            type=event_type,
            payload={"output": output},
            status="ok" if code == 0 else "failed",
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    main()
