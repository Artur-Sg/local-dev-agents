from pathlib import Path

from agents.project_lead import (
    decide_after_failure,
    decompose_task,
    parse_failure_decision,
    parse_subtask_selection,
    parse_task_plan,
    select_next_subtask,
)
from agents.developer import fix_review, fix_tests, fix_visual, generate_solution
from agents.reviewer import review_changes
from adapters.test_runner import run_tests
from adapters.git import get_git_review_text, has_uncommitted_changes
from visual_qa import run_visual_check
from core.actions import CALL_MODEL, READ_CHANGES, READ_STATUS, REVIEW_DIFF, RUN_TESTS, RUN_VISUAL_CHECK, WRITE_FILES
from core.capabilities import DECIDE_AFTER_FAILURE, DECOMPOSE_TASK, FIX_REVIEW, FIX_TESTS, FIX_VISUAL, GENERATE_SOLUTION, PREPARE_TASK, REVIEW_CHANGES, RUN_TESTS as RUN_TESTS_CAPABILITY, SELECT_NEXT_SUBTASK, VISUAL_CHECK
from core.events import AgentEvent, emit_event
from core.run_models import RunSession, get_current_subtask, get_open_subtasks, is_terminal_status
from core.run_store import save_run
from core.settings import ROOT
from core.runtime import use_run
from core.verification_plan import (
    build_verification_plan,
    get_incremental_rules_text,
    get_verification_plan_text,
)
from core.workflow import Step, run_step
from file_blocks import write_file_blocks
from project_context import build_allowed_paths_text, build_project_context
from prompts import render_prompt


def _emit_session_event(session: RunSession, role: str, event_type: str, **kwargs: object) -> None:
    emit_event(
        AgentEvent(
            role=role,
            type=event_type,
            task_id=session.run_id,
            **kwargs,
        )
    )


def _get_generator(capability: str):
    mapping = {
        GENERATE_SOLUTION: generate_solution,
        FIX_TESTS: fix_tests,
        FIX_VISUAL: fix_visual,
        FIX_REVIEW: fix_review,
    }

    generator = mapping.get(capability)
    if generator is None:
        raise ValueError(f"Unsupported generation capability: {capability}")

    return generator


def _find_subtask_by_id(session: RunSession, subtask_id: str):
    for subtask in session.subtasks:
        if subtask.id == subtask_id:
            return subtask

    raise ValueError(f"Unknown subtask selected by project lead: {subtask_id}")


def _build_subtask_prompt(session: RunSession, subtask) -> str:
    verification_plan = _get_session_verification_plan(session)
    lines = _build_subtask_outline(session, subtask)
    lines.extend(
        [
            "",
            "Allowed output paths:",
            build_allowed_paths_text(),
            "",
            get_verification_plan_text(verification_plan),
            "",
            "Incremental delivery rules:",
            get_incremental_rules_text(verification_plan),
            "",
            "Current project files:",
            "",
            build_project_context(),
            "",
            "Return only file blocks and use only the allowed output paths listed above.",
        ]
    )
    return "\n".join(lines).strip()


def _build_subtask_outline(session: RunSession, subtask) -> list[str]:
    lines = [
        session.task_text.strip(),
        "",
        "Current subtask:",
        f"- id: {subtask.id}",
        f"- title: {subtask.title}",
    ]

    if subtask.description:
        lines.append(f"- description: {subtask.description}")

    if subtask.acceptance_criteria:
        lines.append("- acceptance criteria:")
        lines.extend(f"  - {item}" for item in subtask.acceptance_criteria)

    return lines


def _plan_subtasks(session: RunSession) -> None:
    response = run_step(
        Step(
            name="decompose_task",
            action=CALL_MODEL,
            role="orchestrator",
            capability=DECOMPOSE_TASK,
            func=decompose_task,
            args=(session.task_text,),
        )
    )
    summary, subtasks = parse_task_plan(response, session.task_text)
    session.plan_summary = summary
    session.subtasks = subtasks
    save_run(session)
    _emit_session_event(
        session,
        "orchestrator",
        "task_planned",
        payload={"summary": summary, "subtask_count": len(subtasks)},
        status="ok",
    )


def _select_active_subtask(session: RunSession) -> None:
    open_subtasks = get_open_subtasks(session)
    if not open_subtasks:
        session.current_subtask_id = None
        session.status = "done"
        save_run(session)
        _emit_session_event(session, "orchestrator", "workflow_pass", status="ok")
        return

    response = run_step(
        Step(
            name="select_next_subtask",
            action=CALL_MODEL,
            role="orchestrator",
            capability=SELECT_NEXT_SUBTASK,
            func=select_next_subtask,
            args=(session.task_text, open_subtasks),
        )
    )
    subtask_id, reason = parse_subtask_selection(response)
    subtask = _find_subtask_by_id(session, subtask_id)
    if subtask.status == "done":
        raise ValueError(f"Project lead selected completed subtask: {subtask_id}")

    session.current_subtask_id = subtask.id
    subtask.status = "in_progress"
    session.current_prompt = _build_subtask_prompt(session, subtask)
    session.next_capability = GENERATE_SOLUTION
    save_run(session)
    _emit_session_event(
        session,
        "orchestrator",
        "subtask_selected",
        payload={"subtask_id": subtask.id, "title": subtask.title, "reason": reason},
        status="ok",
    )


def _decide_after_failure(session: RunSession, failure_kind: str, failure_details: str) -> tuple[str, str]:
    subtask = get_current_subtask(session)
    if subtask is None:
        raise ValueError("No active subtask while deciding after failure")

    allowed_decisions_by_kind = {
        "test_failure": [FIX_TESTS, "needs_human"],
        "visual_failure": [FIX_VISUAL, "needs_human"],
        "review_failure": [FIX_REVIEW, FIX_VISUAL, FIX_TESTS, "needs_human"],
    }
    allowed_decisions = allowed_decisions_by_kind.get(failure_kind, ["needs_human"])

    response = run_step(
        Step(
            name=f"decide_after_{failure_kind}",
            action=CALL_MODEL,
            role="orchestrator",
            capability=DECIDE_AFTER_FAILURE,
            func=decide_after_failure,
            args=(
                session.task_text,
                subtask,
                failure_kind,
                failure_details,
                session.attempt_count,
                session.max_attempts,
                allowed_decisions,
            ),
        )
    )
    return parse_failure_decision(response, allowed_decisions)


def _set_rework_from_decision(
    session: RunSession,
    subtask,
    decision: str,
    *,
    test_output: str = "",
    diff: str = "",
    review: str = "",
    visual_details: str = "",
) -> None:
    verification_plan = _get_session_verification_plan(session)
    if subtask is not None:
        original_task = "\n".join(_build_subtask_outline(session, subtask)).strip()
    else:
        original_task = session.task_text
    project_context = build_project_context()
    allowed_paths = build_allowed_paths_text()

    if decision == FIX_TESTS:
        prompt_input = test_output
        if not prompt_input:
            raise ValueError("FIX_TESTS requires test_output context")
        session.current_prompt = render_prompt(
            "test_fix",
            original_task=original_task,
            current_project_files=project_context,
            allowed_paths=allowed_paths,
            test_output=prompt_input,
            incremental_rules=get_incremental_rules_text(verification_plan),
            required_file_format=render_prompt("required_file_format", allowed_paths=allowed_paths),
        )
        session.next_capability = FIX_TESTS
        session.status = "needs_rework"
        save_run(session)
        return

    if decision == FIX_VISUAL:
        findings = visual_details or review
        if not findings:
            raise ValueError("FIX_VISUAL requires visual or review findings context")
        session.current_prompt = render_prompt(
            "visual_fix",
            original_task=original_task,
            current_project_files=project_context,
            allowed_paths=allowed_paths,
            visual_findings=findings,
            incremental_rules=get_incremental_rules_text(verification_plan),
            required_file_format=render_prompt("required_file_format", allowed_paths=allowed_paths),
        )
        session.next_capability = FIX_VISUAL
        session.status = "needs_rework"
        save_run(session)
        return

    if decision == FIX_REVIEW:
        session.current_prompt = render_prompt(
            "review_fix",
            original_task=original_task,
            current_project_files=project_context,
            allowed_paths=allowed_paths,
            diff=diff,
            review=review,
            incremental_rules=get_incremental_rules_text(verification_plan),
            required_file_format=render_prompt("required_file_format", allowed_paths=allowed_paths),
        )
        session.next_capability = FIX_REVIEW
        session.status = "needs_rework"
        save_run(session)
        return

    raise ValueError(f"Unsupported rework decision: {decision}")


def _apply_generated_files(
    session: RunSession,
    attempt: int,
    capability: str,
    answer: str,
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
        verification_plan = _get_session_verification_plan(session)
        _emit_session_event(
            session,
            "developer",
            "bad_format",
            payload={"error": str(exc)},
            status="failed",
        )
        prompt = render_prompt(
            "format_fix",
            original_task=session.task_text,
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
        return None, prompt

    written_files = [str(path.relative_to(ROOT)) for path in written]
    session.artifacts["written_files"] = written_files
    _emit_session_event(
        session,
        "developer",
        "files_written",
        payload={"files": written_files},
        status="ok",
    )
    return written, None


def _prepare_session(session: RunSession) -> RunSession:
    _emit_session_event(session, "orchestrator", "task_started", status="started")
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
        session.human_summary = "Sandbox не чистый. Нужен approve или reject перед новым запуском."
        session.status = "needs_human"
        save_run(session)
        _emit_session_event(session, "orchestrator", "run_blocked_dirty", status="blocked")
        return session

    session.artifacts["verification_plan"] = build_verification_plan()
    save_run(session)
    _emit_session_event(
        session,
        "orchestrator",
        "verification_planned",
        payload={"verification_plan": session.artifacts["verification_plan"]},
        status="ok",
    )

    _plan_subtasks(session)
    _select_active_subtask(session)
    if session.status == "done":
        return session

    session.status = "executing"
    save_run(session)
    _emit_session_event(session, "orchestrator", "task_loaded", status="ok")
    return session


def _get_session_verification_plan(session: RunSession) -> dict[str, object]:
    plan = session.artifacts.get("verification_plan")

    if isinstance(plan, dict) and plan:
        return plan

    plan = build_verification_plan()
    session.artifacts["verification_plan"] = plan
    return plan


def run_once(session: RunSession) -> RunSession:
    if is_terminal_status(session.status):
        return session

    if session.status == "planning":
        return _prepare_session(session)

    if session.status == "needs_rework":
        session.status = "executing"
        save_run(session)

    if session.attempt_count >= session.max_attempts:
        session.status = "blocked"
        save_run(session)
        _emit_session_event(session, "orchestrator", "workflow_final_fail", status="failed")
        return session

    session.status = "executing"
    attempt = session.attempt_count + 1
    capability = session.next_capability
    prompt = session.current_prompt
    generator = _get_generator(capability)

    _emit_session_event(
        session,
        "developer",
        "generation_started",
        payload={"capability": capability},
        status="started",
    )
    answer = run_step(
        Step(
            name=f"attempt_{attempt}_{capability}_generate",
            action=CALL_MODEL,
            role="developer",
            capability=capability,
            func=generator,
            args=(prompt,),
        )
    )

    written, retry_prompt = _apply_generated_files(session, attempt, capability, answer)
    session.attempt_count = attempt
    subtask = get_current_subtask(session)
    if subtask is not None:
        subtask.attempts = attempt

    if written is None:
        session.current_prompt = retry_prompt or session.current_prompt
        session.next_capability = capability
        session.status = "needs_rework"
        save_run(session)
        return session

    session.status = "testing"
    _emit_session_event(session, "tester", "tests_started", status="started")
    code, output = run_step(
        Step(
            name=f"attempt_{attempt}_run_tests",
            action=RUN_TESTS,
            role="tester",
            capability=RUN_TESTS_CAPABILITY,
            func=run_tests,
        )
    )
    session.last_test_output = output
    test_event_type = "tests_passed" if code == 0 else "tests_failed"
    _emit_session_event(
        session,
        "tester",
        test_event_type,
        payload={"output": output},
        status="ok" if code == 0 else "failed",
    )

    if code != 0:
        _emit_session_event(session, "tester", "workflow_fail", status="failed")
        decision, reason = _decide_after_failure(session, "test_failure", output)
        if decision == "needs_human":
            session.human_summary = reason
            session.status = "needs_human"
            save_run(session)
            _emit_session_event(
                session,
                "orchestrator",
                "needs_human",
                payload={"reason": reason},
                status="blocked",
            )
            return session

        _set_rework_from_decision(
            session,
            subtask,
            decision,
            test_output=output,
        )
        return session

    _emit_session_event(session, "tester", "visual_check_started", status="started")
    visual_result = run_step(
        Step(
            name=f"attempt_{attempt}_visual_check",
            action=RUN_VISUAL_CHECK,
            role="tester",
            capability=VISUAL_CHECK,
            func=run_visual_check,
        )
    )
    session.artifacts["visual_check"] = {
        "passed": visual_result.passed,
        "summary": visual_result.summary,
        "details": visual_result.details,
        "metrics": visual_result.metrics,
    }
    visual_event_type = (
        "visual_check_skipped"
        if visual_result.skipped
        else "visual_check_passed" if visual_result.passed else "visual_check_failed"
    )
    _emit_session_event(
        session,
        "tester",
        visual_event_type,
        payload={
            "summary": visual_result.summary,
            "details": visual_result.details,
        },
        status="ok" if visual_result.passed else "failed",
    )

    if not visual_result.skipped and not visual_result.passed:
        visual_details = "\n".join(f"- {item}" for item in visual_result.details) or visual_result.summary
        decision, reason = _decide_after_failure(session, "visual_failure", visual_details)
        if decision == "needs_human":
            session.human_summary = reason
            session.status = "needs_human"
            save_run(session)
            _emit_session_event(
                session,
                "orchestrator",
                "needs_human",
                payload={"reason": reason},
                status="blocked",
            )
            return session

        _set_rework_from_decision(
            session,
            subtask,
            decision,
            visual_details=visual_details,
        )
        return session

    session.status = "reviewing"
    diff = run_step(
        Step(
            name=f"attempt_{attempt}_review_read_changes",
            action=READ_CHANGES,
            role="reviewer",
            capability=REVIEW_CHANGES,
            func=get_git_review_text,
        )
    )
    _emit_session_event(session, "reviewer", "review_started", status="started")
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
    session.last_review = review

    if review.strip().upper().startswith("APPROVE"):
        if subtask is not None:
            subtask.status = "done"
        _emit_session_event(
            session,
            "reviewer",
            "review_approved",
            payload={"review": review, "diff": diff},
            status="approved",
        )
        if subtask is not None:
            _emit_session_event(
                session,
                "orchestrator",
                "subtask_completed",
                payload={"subtask_id": subtask.id, "title": subtask.title},
                status="ok",
            )
        _select_active_subtask(session)
        if session.status != "done":
            session.status = "executing"
            save_run(session)
        return session

    _emit_session_event(
        session,
        "reviewer",
        "review_requested_changes",
        payload={"review": review, "diff": diff},
        status="changes_requested",
    )
    decision, reason = _decide_after_failure(session, "review_failure", review)
    if decision == "needs_human":
        session.human_summary = reason
        session.status = "needs_human"
        save_run(session)
        _emit_session_event(
            session,
            "orchestrator",
            "needs_human",
            payload={"reason": reason},
            status="blocked",
        )
        return session

    _set_rework_from_decision(
        session,
        subtask,
        decision,
        diff=diff,
        review=review,
    )
    return session


def run_until_terminal(session: RunSession) -> RunSession:
    with use_run(session.run_id):
        while not is_terminal_status(session.status):
            session = run_once(session)

    return session
