from core.actions import READ_TASK
from core.capabilities import PREPARE_TASK
from core.session import create_session, save_session
from core.state_machine import run_until_terminal
from core.workflow import Step, clear_trace, run_step
from env import get_agent_max_attempts
from reporters.console import setup_console_reporting
from task_source import read_current_task


def main() -> None:
    clear_trace()
    task_text = run_step(
        Step(
            name="read_current_task",
            action=READ_TASK,
            role="orchestrator",
            capability=PREPARE_TASK,
            func=read_current_task,
        )
    )
    session = create_session(task_text, get_agent_max_attempts())
    save_session(session)
    session = run_until_terminal(session)
    raise SystemExit(0 if session.status == "done" else 1)


if __name__ == "__main__":
    setup_console_reporting()
    main()
