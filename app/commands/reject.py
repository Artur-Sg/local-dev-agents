from adapters.git_write import restore_changes, verify_reject_request
from core.actions import REJECT_CHANGES, RESTORE_CHANGES
from core.capabilities import REJECT_CHANGES_CAPABILITY, RESTORE_REJECTED_CHANGES
from core.events import AgentEvent, emit_event
from core.workflow import Step, clear_trace, run_step
from reporters.console import setup_console_reporting


def main() -> None:
    setup_console_reporting()
    clear_trace()
    run_step(
        Step(
            name="reject_request",
            action=REJECT_CHANGES,
            role="human_operator",
            capability=REJECT_CHANGES_CAPABILITY,
            func=verify_reject_request,
        )
    )
    run_step(
        Step(
            name="reject_restore",
            action=RESTORE_CHANGES,
            role="system_committer",
            capability=RESTORE_REJECTED_CHANGES,
            func=restore_changes,
        )
    )
    emit_event(AgentEvent(role="system_committer", type="changes_rejected", status="ok"))


if __name__ == "__main__":
    main()
