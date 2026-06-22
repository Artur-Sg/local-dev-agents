from adapters.git import get_git_review_text
from adapters.git_write import commit_changes, verify_approval_for_diff
from core.actions import APPROVE_CHANGES, COMMIT_CHANGES, READ_CHANGES
from core.capabilities import APPROVE_CHANGES_CAPABILITY, COMMIT_APPROVED_CHANGES, INSPECT_CHANGES
from core.events import AgentEvent, emit_event
from core.workflow import Step, clear_trace, run_step
from reporters.console import setup_console_reporting


def main() -> None:
    setup_console_reporting()
    clear_trace()

    changes = run_step(
        Step(
            name="approve_read_changes",
            action=READ_CHANGES,
            role="human_operator",
            capability=INSPECT_CHANGES,
            func=get_git_review_text,
        )
    )

    emit_event(
        AgentEvent(
            role="human_operator",
            type="approval_diff",
            payload={"diff": changes},
            status="review",
        )
    )

    run_step(
        Step(
            name="approve_request",
            action=APPROVE_CHANGES,
            role="human_operator",
            capability=APPROVE_CHANGES_CAPABILITY,
            func=verify_approval_for_diff,
            args=(changes,),
        )
    )

    output = run_step(
        Step(
            name="approve_commit",
            action=COMMIT_CHANGES,
            role="system_committer",
            capability=COMMIT_APPROVED_CHANGES,
            func=commit_changes,
        )
    )

    emit_event(
        AgentEvent(
            role="system_committer",
            type="changes_committed",
            payload={"output": output},
            status="ok",
        )
    )


if __name__ == "__main__":
    main()
