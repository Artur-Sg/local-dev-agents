import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from core.capabilities import GENERATE_SOLUTION
from core.settings import ROOT

RUNS_DIR = ROOT / "runs"


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


def get_runs_dir() -> Path:
    return RUNS_DIR


def get_run_dir(run_id: str) -> Path:
    return get_runs_dir() / run_id


def get_state_path(run_id: str) -> Path:
    return get_run_dir(run_id) / "state.json"


def get_events_path(run_id: str) -> Path:
    return get_run_dir(run_id) / "events.jsonl"


def is_terminal_status(status: str) -> bool:
    return status in {"done", "blocked", "needs_human"}


def create_session(task_text: str, max_attempts: int, task_file: str = "") -> RunSession:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_id = f"{timestamp}-{uuid4().hex[:6]}"

    return RunSession(
        run_id=run_id,
        task_file=task_file,
        task_text=task_text,
        status="planning",
        attempt_count=0,
        max_attempts=max_attempts,
        current_subtask_id=None,
        subtasks=[],
        current_prompt=task_text,
        next_capability=GENERATE_SOLUTION,
        plan_summary="",
        human_summary="",
        artifacts={"written_files": []},
    )


def save_session(session: RunSession) -> None:
    run_dir = get_run_dir(session.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    get_state_path(session.run_id).write_text(
        json.dumps(asdict(session), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_session(run_id: str) -> RunSession:
    data = json.loads(get_state_path(run_id).read_text(encoding="utf-8"))
    subtasks = [Subtask(**subtask) for subtask in data.get("subtasks", [])]
    return RunSession(
        run_id=data["run_id"],
        task_file=data.get("task_file", ""),
        task_text=data["task_text"],
        status=data["status"],
        attempt_count=data["attempt_count"],
        max_attempts=data["max_attempts"],
        current_subtask_id=data.get("current_subtask_id"),
        subtasks=subtasks,
        current_prompt=data["current_prompt"],
        next_capability=data["next_capability"],
        plan_summary=data.get("plan_summary", ""),
        human_summary=data.get("human_summary", ""),
        last_test_output=data.get("last_test_output", ""),
        last_review=data.get("last_review", ""),
        artifacts=data.get("artifacts", {}),
    )


def find_latest_resumable_session() -> RunSession | None:
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return None

    candidates: list[Path] = []
    for run_dir in runs_dir.iterdir():
        state_path = run_dir / "state.json"
        if state_path.exists():
            candidates.append(state_path)

    for state_path in sorted(candidates, reverse=True):
        session = load_session(state_path.parent.name)
        if not is_terminal_status(session.status):
            return session

    return None


def get_current_subtask(session: RunSession) -> Subtask | None:
    if session.current_subtask_id is None:
        return None

    for subtask in session.subtasks:
        if subtask.id == session.current_subtask_id:
            return subtask

    return None


def get_open_subtasks(session: RunSession) -> list[Subtask]:
    return [subtask for subtask in session.subtasks if subtask.status != "done"]


def find_latest_session_for_task(task_file: str) -> RunSession | None:
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return None

    candidates: list[Path] = []
    for run_dir in runs_dir.iterdir():
        state_path = run_dir / "state.json"
        if state_path.exists():
            candidates.append(state_path)

    for state_path in sorted(candidates, reverse=True):
        session = load_session(state_path.parent.name)
        if session.task_file == task_file:
            return session

    return None


def list_sessions() -> list[RunSession]:
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return []

    sessions: list[RunSession] = []
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        state_path = run_dir / "state.json"
        if not state_path.exists():
            continue
        sessions.append(load_session(run_dir.name))

    return sessions


def find_session(run_id: str) -> RunSession | None:
    state_path = get_state_path(run_id)
    if not state_path.exists():
        return None
    return load_session(run_id)
