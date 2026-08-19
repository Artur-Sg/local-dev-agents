from dataclasses import dataclass, field


@dataclass
class Subtask:
    id: str
    title: str
    description: str = ""
    status: str = "todo"
    attempts: int = 0
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class RunSession:
    run_id: str
    task_file: str
    task_text: str
    status: str
    attempt_count: int
    max_attempts: int
    current_subtask_id: str | None
    subtasks: list[Subtask]
    current_prompt: str
    next_capability: str
    plan_summary: str = ""
    human_summary: str = ""
    last_test_output: str = ""
    last_review: str = ""
    artifacts: dict[str, object] = field(default_factory=dict)


def is_terminal_status(status: str) -> bool:
    return status in {"done", "blocked", "needs_human"}


def get_current_subtask(session: RunSession) -> Subtask | None:
    if session.current_subtask_id is None:
        return None

    for subtask in session.subtasks:
        if subtask.id == session.current_subtask_id:
            return subtask

    return None


def get_open_subtasks(session: RunSession) -> list[Subtask]:
    return [subtask for subtask in session.subtasks if subtask.status != "done"]
