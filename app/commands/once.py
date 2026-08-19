from pathlib import Path

from agents.developer import generate_solution
from adapters.test_runner import run_tests
from core.verification_plan import build_verification_plan, get_incremental_rules_text
from core.actions import CALL_MODEL, READ_TASK, RUN_TESTS, WRITE_FILES
from core.capabilities import GENERATE_SOLUTION, PREPARE_TASK, RUN_TESTS as RUN_TESTS_CAPABILITY
from core.events import AgentEvent, emit_event
from core.task_store import list_tasks, read_task_text
from env import get_agent_max_attempts
from core.workflow import Step, clear_trace, run_step
from file_blocks import write_file_blocks
from project_context import build_allowed_paths_text, build_project_context
from prompts import render_prompt
from reporters.console import setup_console_reporting

ROOT = Path(__file__).resolve().parents[2]
ONCE_MAX_FORMAT_ATTEMPTS = min(get_agent_max_attempts(), 3)


def _generate_files_with_format_retry(prompt: str) -> list[Path]:
    verification_plan = build_verification_plan()
    current_prompt = prompt
    last_error: Exception | None = None

    for attempt in range(1, ONCE_MAX_FORMAT_ATTEMPTS + 1):
        answer = run_step(
            Step(
                name=f"generate_solution_attempt_{attempt}",
                action=CALL_MODEL,
                role="developer",
                capability=GENERATE_SOLUTION,
                func=generate_solution,
                args=(current_prompt,),
            )
        )

        try:
            return run_step(
                Step(
                    name=f"apply_solution_files_attempt_{attempt}",
                    action=WRITE_FILES,
                    role="developer",
                    capability=GENERATE_SOLUTION,
                    func=write_file_blocks,
                    args=(answer,),
                )
            )
        except Exception as exc:
            last_error = exc
            emit_event(
                AgentEvent(
                    role="developer",
                    type="bad_format",
                    payload={"error": str(exc)},
                    status="failed",
                )
            )
            current_prompt = render_prompt(
                "format_fix",
                original_task=prompt,
                current_project_files=build_project_context(),
                allowed_paths=build_allowed_paths_text(),
                bad_answer=answer,
                error=str(exc),
                incremental_rules=get_incremental_rules_text(verification_plan),
                required_file_format=render_prompt(
                    "required_file_format",
                    allowed_paths=build_allowed_paths_text(),
                ),
            )

    if last_error is None:
        raise RuntimeError("Failed to generate file blocks for an unknown reason")

    raise last_error


def main() -> None:
    setup_console_reporting()
    clear_trace()
    inbox_records = list_tasks("inbox")
    if not inbox_records:
        raise SystemExit("once expects one inbox task. Use ./agent.sh kickoff to prepare a task first.")
    if len(inbox_records) > 1:
        raise SystemExit("once expects a single inbox task. Use ./agent.sh auto for queued execution.")

    task_file = str(inbox_records[0]["task_file"])
    emit_event(AgentEvent(role="orchestrator", type="task_started", status="started"))
    prompt = run_step(
        Step(
            name="read_inbox_task",
            action=READ_TASK,
            role="orchestrator",
            capability=PREPARE_TASK,
            func=read_task_text,
            args=(task_file,),
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
    written = _generate_files_with_format_retry(prompt)
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
    emit_event(
        AgentEvent(
            role="tester",
            type=test_event_type,
            payload={"output": output},
            status="ok" if code == 0 else "failed",
        )
    )

    if code == 0:
        emit_event(AgentEvent(role="orchestrator", type="workflow_pass", status="ok"))
    else:
        emit_event(AgentEvent(role="tester", type="workflow_fail", status="failed"))

    raise SystemExit(code)


if __name__ == "__main__":
    main()
