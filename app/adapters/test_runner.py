import subprocess
import shlex

from core.actions import RUN_TESTS
from core.capabilities import RUN_TESTS as RUN_TESTS_CAPABILITY
from core.events import AgentEvent, emit_event
from core.roles import require_action
from core.settings import ROOT, get_project_dir
from core.verification_plan import get_active_test_runner
from core.workflow import Step, run_step
from reporters.console import setup_console_reporting

def run_tests() -> tuple[int, str]:
    require_action(RUN_TESTS)
    test_runner = get_active_test_runner()
    runner_type = str(test_runner["type"]).strip()

    if runner_type == "docker":
        return _run_docker_tests(test_runner)

    if runner_type == "local":
        return _run_local_tests(test_runner)

    raise ValueError(f"Unsupported test runner type at runtime: {runner_type}")


def _build_shell_command(test_runner: dict[str, object]) -> list[str]:
    setup_commands = list(test_runner["setup_commands"])
    base_command = shlex.join(test_runner["command"])

    if setup_commands:
        joined_setup = " && ".join(setup_commands)
        return ["sh", "-lc", f"{joined_setup} && {base_command}"]

    return list(test_runner["command"])


def _run_docker_tests(test_runner: dict[str, object]) -> tuple[int, str]:
    project_dir = get_project_dir()
    runner_command = _build_shell_command(test_runner)
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
        f"{project_dir}:/workspace",
        "-w",
        "/workspace",
        test_runner["image"],
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


def _run_local_tests(test_runner: dict[str, object]) -> tuple[int, str]:
    project_dir = get_project_dir()
    command = _build_shell_command(test_runner)
    proc = subprocess.run(
        command,
        cwd=project_dir,
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
    if output.strip():
        emit_event(
            AgentEvent(
                role="tester",
                type="raw_output",
                payload={"output": output},
                status="ok" if code == 0 else "failed",
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
