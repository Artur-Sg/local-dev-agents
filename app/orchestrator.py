from pathlib import Path

from agents.developer import fix_review, fix_tests, generate_solution
from agents.reviewer import review_changes
from adapters.docker import run_tests
from adapters.git import get_git_review_text, has_uncommitted_changes
from core.actions import CALL_MODEL, READ_CHANGES, READ_STATUS, READ_TASK, REVIEW_DIFF, RUN_TESTS, WRITE_FILES
from core.capabilities import FIX_REVIEW, FIX_TESTS, GENERATE_SOLUTION, PREPARE_TASK, REVIEW_CHANGES, RUN_TESTS as RUN_TESTS_CAPABILITY
from core.events import AgentEvent, emit_event
from core.settings import ROOT
from core.workflow import Step, clear_trace, run_step
from env import get_agent_max_attempts
from file_blocks import write_file_blocks
from prompts import render_prompt
from task_source import read_current_task

MAX_ATTEMPTS = get_agent_max_attempts()


def _apply_generated_files(
    attempt: int,
    capability: str,
    answer: str,
    original_task: str,
) -> tuple[list[Path] | None, str | None]:
    try:
        written = run_step(
            Step(
                name=f"attempt_{attempt}_{capability}_apply_files",
                action=WRITE_FILES,
                role="developer",
                capability=capability,
                func=write_file_blocks,
                args=(answer,),
            )
        )
    except Exception as exc:
        emit_event(
            AgentEvent(
                role="developer",
                type="bad_format",
                payload={"error": str(exc)},
                status="failed",
            )
        )
        prompt = render_prompt(
            "format_fix",
            original_task=original_task,
            bad_answer=answer,
            error=str(exc),
            required_file_format=render_prompt("required_file_format"),
        )
        return None, prompt

    emit_event(
        AgentEvent(
            role="developer",
            type="files_written",
            payload={"files": [str(path.relative_to(ROOT)) for path in written]},
            status="ok",
        )
    )
    return written, None


def _generate_with_capability(
    attempt: int,
    capability: str,
    prompt: str,
    generator,
) -> str:
    emit_event(
        AgentEvent(
            role="developer",
            type="generation_started",
            payload={
                "attempt": attempt,
                "max_attempts": MAX_ATTEMPTS,
                "capability": capability,
            },
            status="started",
        )
    )
    return run_step(
        Step(
            name=f"attempt_{attempt}_{capability}_generate",
            action=CALL_MODEL,
            role="developer",
            capability=capability,
            func=generator,
            args=(prompt,),
        )
    )


def main() -> None:
    clear_trace()
    emit_event(AgentEvent(role="orchestrator", type="task_started", status="started"))
    dirty = run_step(
        Step(
            name="check_worktree_clean",
            action=READ_STATUS,
            role="orchestrator",
            capability=PREPARE_TASK,
            func=has_uncommitted_changes,
        )
    )

    if dirty:
        emit_event(AgentEvent(role="orchestrator", type="run_blocked_dirty", status="blocked"))
        raise SystemExit(1)

    original_task = run_step(
        Step(
            name="read_current_task",
            action=READ_TASK,
            role="orchestrator",
            capability=PREPARE_TASK,
            func=read_current_task,
        )
    )
    emit_event(AgentEvent(role="orchestrator", type="task_loaded", status="ok"))
    prompt = original_task

    for attempt in range(1, MAX_ATTEMPTS + 1):
        capability = GENERATE_SOLUTION if attempt == 1 else FIX_TESTS
        generator = generate_solution if attempt == 1 else fix_tests
        answer = _generate_with_capability(attempt, capability, prompt, generator)

        written, retry_prompt = _apply_generated_files(attempt, capability, answer, original_task)
        if written is None:
            prompt = retry_prompt or prompt
            continue

        emit_event(AgentEvent(role="tester", type="tests_started", status="started"))
        code, output = run_step(
            Step(
                name=f"attempt_{attempt}_run_tests",
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

        if code != 0:
            emit_event(AgentEvent(role="tester", type="workflow_fail", status="failed"))
            prompt = render_prompt(
                "test_fix",
                original_task=original_task,
                test_output=output,
                required_file_format=render_prompt("required_file_format"),
            )
            continue

        diff = run_step(
            Step(
                name=f"attempt_{attempt}_review_read_changes",
                action=READ_CHANGES,
                role="reviewer",
                capability=REVIEW_CHANGES,
                func=get_git_review_text,
            )
        )
        emit_event(AgentEvent(role="reviewer", type="review_started", status="started"))
        review = run_step(
            Step(
                name=f"attempt_{attempt}_review_decide",
                action=REVIEW_DIFF,
                role="reviewer",
                capability=REVIEW_CHANGES,
                func=review_changes,
                args=(diff,),
            )
        )

        if review.strip().upper().startswith("APPROVE"):
            emit_event(
                AgentEvent(
                    role="reviewer",
                    type="review_approved",
                    payload={"review": review, "diff": diff},
                    status="approved",
                )
            )
            emit_event(AgentEvent(role="orchestrator", type="workflow_pass", status="ok"))
            raise SystemExit(0)

        emit_event(
            AgentEvent(
                role="reviewer",
                type="review_requested_changes",
                payload={"review": review, "diff": diff},
                status="changes_requested",
            )
        )

        fix_prompt = render_prompt(
            "review_fix",
            original_task=original_task,
            diff=diff,
            review=review,
            required_file_format=render_prompt("required_file_format"),
        )
        answer = _generate_with_capability(attempt, FIX_REVIEW, fix_prompt, fix_review)

        written, retry_prompt = _apply_generated_files(attempt, FIX_REVIEW, answer, original_task)
        if written is None:
            prompt = retry_prompt or prompt
            continue

        prompt = fix_prompt

    emit_event(AgentEvent(role="orchestrator", type="workflow_final_fail", status="failed"))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
