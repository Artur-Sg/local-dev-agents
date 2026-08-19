from core.actions import READ_TASK
from core.capabilities import PREPARE_TASK
from core.run_store import create_run, save_run
from core.task_store import (
    list_tasks,
    mark_in_progress,
    move_to_blocked,
    move_to_done,
    move_to_needs_human,
    read_task_text,
)
from core.state_machine import run_until_terminal
from core.workflow import Step, clear_trace, run_step
from env import get_agent_max_attempts
from reporters.console import setup_console_reporting


def main() -> None:
    clear_trace()
    inbox_records = list_tasks("inbox")

    if not inbox_records:
        raise SystemExit("run expects one inbox task. Use ./agent.sh kickoff to prepare a task first.")

    if len(inbox_records) > 1:
        raise SystemExit("run expects a single inbox task. Use ./agent.sh auto for queued execution.")

    task_file = str(inbox_records[0]["task_file"])
    task_text = run_step(
        Step(
            name="read_inbox_task",
            action=READ_TASK,
            role="orchestrator",
            capability=PREPARE_TASK,
            func=read_task_text,
            args=(task_file,),
        )
    )

    session = create_run(task_text, get_agent_max_attempts(), task_file=task_file)
    save_run(session)
    if inbox_records:
        mark_in_progress({"task_file": task_file}, session.run_id)

    session = run_until_terminal(session)

    if session.task_file:
        if session.status == "done":
            move_to_done(session.task_file, session.run_id)
        elif session.status == "needs_human":
            move_to_needs_human(
                session.task_file,
                session.run_id,
                session.human_summary or "Needs human intervention",
            )
        elif session.status == "blocked":
            move_to_blocked(
                session.task_file,
                session.run_id,
                session.human_summary or "Run blocked",
            )

    raise SystemExit(0 if session.status == "done" else 1)


if __name__ == "__main__":
    setup_console_reporting()
    main()
