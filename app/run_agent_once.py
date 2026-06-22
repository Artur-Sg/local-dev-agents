from agents.developer import generate_solution
from adapters.docker import run_tests
from core.actions import CALL_MODEL, READ_TASK, RUN_TESTS, WRITE_FILES
from core.capabilities import GENERATE_SOLUTION, PREPARE_TASK, RUN_TESTS as RUN_TESTS_CAPABILITY
from core.events import AgentEvent, emit_event
from core.workflow import Step, clear_trace, run_step
from file_blocks import write_file_blocks
from pathlib import Path
from reporters.console import setup_console_reporting
from task_source import read_current_task

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    setup_console_reporting()
    clear_trace()
    emit_event(AgentEvent(role="orchestrator", type="task_started", status="started"))
    prompt = run_step(
        Step(
            name="read_current_task",
            action=READ_TASK,
            role="orchestrator",
            capability=PREPARE_TASK,
            func=read_current_task,
        )
    )
    emit_event(AgentEvent(role="orchestrator", type="task_loaded", status="ok"))

    emit_event(
        AgentEvent(
            role="developer",
            type="generation_started",
            payload={"capability": GENERATE_SOLUTION},
            status="started",
        )
    )
    answer = run_step(
        Step(
            name="generate_solution",
            action=CALL_MODEL,
            role="developer",
            capability=GENERATE_SOLUTION,
            func=generate_solution,
            args=(prompt,),
        )
    )

    written = run_step(
        Step(
            name="apply_solution_files",
            action=WRITE_FILES,
            role="developer",
            capability=GENERATE_SOLUTION,
            func=write_file_blocks,
            args=(answer,),
        )
    )
    emit_event(
        AgentEvent(
            role="developer",
            type="files_written",
            payload={"files": [str(path.relative_to(ROOT)) for path in written]},
            status="ok",
        )
    )

    emit_event(AgentEvent(role="tester", type="tests_started", status="started"))
    code, output = run_step(
        Step(
            name="run_tests",
            action=RUN_TESTS,
            role="tester",
            capability=RUN_TESTS_CAPABILITY,
            func=run_tests,
        )
    )
    test_event_type = "tests_passed" if code == 0 else "tests_failed"
    emit_event(AgentEvent(role="tester", type=test_event_type, payload={"output": output}, status="ok" if code == 0 else "failed"))

    if code == 0:
        emit_event(AgentEvent(role="orchestrator", type="workflow_pass", status="ok"))
    else:
        emit_event(AgentEvent(role="tester", type="workflow_fail", status="failed"))

    raise SystemExit(code)


if __name__ == "__main__":
    main()
