import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from core.capabilities import GENERATE_SOLUTION
from core.db import (
    find_latest_resumable_run_record,
    get_run_record,
    get_run_subtasks,
    init_db,
    list_run_records,
    upsert_run_record,
)
from core.run_models import RunSession, Subtask
from core.settings import ROOT

RUNS_DIR = ROOT / "runs"


def get_runs_dir() -> Path:
    return RUNS_DIR


def get_run_dir(run_id: str) -> Path:
    return get_runs_dir() / run_id


def get_state_path(run_id: str) -> Path:
    return get_run_dir(run_id) / "state.json"


def get_events_path(run_id: str) -> Path:
    return get_run_dir(run_id) / "events.jsonl"


def get_verification_plan_path(run_id: str) -> Path:
    return get_run_dir(run_id) / "verification_plan.json"


def create_session(task_text: str, max_attempts: int, task_file: str = "") -> RunSession:
    init_db()
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


def _serialize_subtasks(session: RunSession) -> list[dict[str, object]]:
    return [
        {
            "run_id": session.run_id,
            "subtask_id": subtask.id,
            "title": subtask.title,
            "description": subtask.description,
            "status": subtask.status,
            "attempts": subtask.attempts,
            "acceptance_criteria_json": json.dumps(subtask.acceptance_criteria, ensure_ascii=False),
            "sort_order": index,
        }
        for index, subtask in enumerate(session.subtasks)
    ]


def _deserialize_record(record: dict[str, object]) -> RunSession:
    subtasks = [
        Subtask(
            id=item["subtask_id"],
            title=item["title"],
            description=item["description"],
            status=item["status"],
            attempts=item["attempts"],
            acceptance_criteria=json.loads(item["acceptance_criteria_json"] or "[]"),
        )
        for item in get_run_subtasks(str(record["run_id"]))
    ]
    return RunSession(
        run_id=str(record["run_id"]),
        task_file=str(record.get("task_file", "")),
        task_text=str(record["task_text"]),
        status=str(record["status"]),
        attempt_count=int(record["attempt_count"]),
        max_attempts=int(record["max_attempts"]),
        current_subtask_id=record.get("current_subtask_id"),
        subtasks=subtasks,
        current_prompt=str(record["current_prompt"]),
        next_capability=str(record["next_capability"]),
        plan_summary=str(record.get("plan_summary", "")),
        human_summary=str(record.get("human_summary", "")),
        last_test_output=str(record.get("last_test_output", "")),
        last_review=str(record.get("last_review", "")),
        artifacts=json.loads(str(record.get("artifacts_json", "{}")) or "{}"),
    )


def _load_session_from_file(run_id: str) -> RunSession:
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


def save_session(session: RunSession) -> None:
    init_db()
    run_dir = get_run_dir(session.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    get_state_path(session.run_id).write_text(
        json.dumps(asdict(session), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    verification_plan = session.artifacts.get("verification_plan")
    if isinstance(verification_plan, dict) and verification_plan:
        get_verification_plan_path(session.run_id).write_text(
            json.dumps(verification_plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    upsert_run_record(
        {
            "run_id": session.run_id,
            "task_file": session.task_file,
            "task_text": session.task_text,
            "status": session.status,
            "attempt_count": session.attempt_count,
            "max_attempts": session.max_attempts,
            "current_subtask_id": session.current_subtask_id,
            "current_prompt": session.current_prompt,
            "next_capability": session.next_capability,
            "plan_summary": session.plan_summary,
            "human_summary": session.human_summary,
            "last_test_output": session.last_test_output,
            "last_review": session.last_review,
            "artifacts_json": json.dumps(session.artifacts, ensure_ascii=False),
        },
        _serialize_subtasks(session),
    )


def load_session(run_id: str) -> RunSession:
    record = get_run_record(run_id)
    if record is not None:
        return _deserialize_record(record)
    return _load_session_from_file(run_id)


def sync_run_sessions_to_db() -> None:
    init_db()
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return

    for run_dir in runs_dir.iterdir():
        state_path = run_dir / "state.json"
        if not state_path.exists():
            continue

        session = _load_session_from_file(run_dir.name)
        existing_record = get_run_record(session.run_id)
        task_file = session.task_file
        if existing_record is not None and str(existing_record.get("task_file", "")).strip():
            task_file = str(existing_record["task_file"])
        upsert_run_record(
            {
                "run_id": session.run_id,
                "task_file": task_file,
                "task_text": session.task_text,
                "status": session.status,
                "attempt_count": session.attempt_count,
                "max_attempts": session.max_attempts,
                "current_subtask_id": session.current_subtask_id,
                "current_prompt": session.current_prompt,
                "next_capability": session.next_capability,
                "plan_summary": session.plan_summary,
                "human_summary": session.human_summary,
                "last_test_output": session.last_test_output,
                "last_review": session.last_review,
                "artifacts_json": json.dumps(session.artifacts, ensure_ascii=False),
            },
            _serialize_subtasks(session),
        )


def find_latest_resumable_session() -> RunSession | None:
    sync_run_sessions_to_db()
    record = find_latest_resumable_run_record()
    if record is not None:
        return load_session(str(record["run_id"]))
    return None


def find_latest_session_for_task(task_file: str) -> RunSession | None:
    sync_run_sessions_to_db()
    for record in list_run_records():
        if record.get("task_file", "") == task_file:
            return load_session(str(record["run_id"]))
    return None


def list_sessions() -> list[RunSession]:
    sync_run_sessions_to_db()
    return [load_session(str(record["run_id"])) for record in list_run_records()]


def find_session(run_id: str) -> RunSession | None:
    sync_run_sessions_to_db()
    record = get_run_record(run_id)
    if record is None and not get_state_path(run_id).exists():
        return None
    return load_session(run_id)
