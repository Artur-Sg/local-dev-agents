import json
import re

from adapters.ollama import call_model
from core.run_models import Subtask


def decompose_task(task_text: str) -> str:
    return call_model(task_text)


def select_next_subtask(task_text: str, subtasks: list[Subtask]) -> str:
    subtasks_json = json.dumps(
        [
            {
                "id": subtask.id,
                "title": subtask.title,
                "description": subtask.description,
                "status": subtask.status,
                "attempts": subtask.attempts,
                "acceptance_criteria": subtask.acceptance_criteria,
            }
            for subtask in subtasks
        ],
        ensure_ascii=False,
        indent=2,
    )
    prompt = (
        "Task:\n"
        f"{task_text.strip()}\n\n"
        "Current subtasks:\n"
        f"{subtasks_json}\n"
    )
    return call_model(prompt)


def select_next_task(task_candidates: list[dict[str, str]]) -> str:
    prompt = (
        "Available tasks:\n"
        f"{json.dumps(task_candidates, ensure_ascii=False, indent=2)}\n"
    )
    return call_model(prompt)


def decide_after_failure(
    task_text: str,
    subtask: Subtask,
    failure_kind: str,
    failure_details: str,
    attempt_count: int,
    max_attempts: int,
    allowed_decisions: list[str],
) -> str:
    subtask_json = json.dumps(
        {
            "id": subtask.id,
            "title": subtask.title,
            "description": subtask.description,
            "status": subtask.status,
            "attempts": subtask.attempts,
            "acceptance_criteria": subtask.acceptance_criteria,
        },
        ensure_ascii=False,
        indent=2,
    )
    prompt = (
        "Task:\n"
        f"{task_text.strip()}\n\n"
        "Current subtask:\n"
        f"{subtask_json}\n\n"
        f"Failure kind: {failure_kind}\n"
        f"Attempt count: {attempt_count}\n"
        f"Max attempts: {max_attempts}\n\n"
        "Allowed decisions:\n"
        f"{json.dumps(allowed_decisions, ensure_ascii=False)}\n\n"
        "Failure details:\n"
        f"{failure_details.strip()}\n"
    )
    return call_model(prompt)


def _extract_json_block(text: str) -> str:
    stripped = text.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Project lead response does not contain a JSON object")

    return stripped[start : end + 1]


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _load_json_object(text: str) -> dict:
    raw = _extract_json_block(text)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        repaired = _strip_trailing_commas(raw)
        data = json.loads(repaired)

    if not isinstance(data, dict):
        raise ValueError("Project lead response must decode to a JSON object")

    return data


def _build_fallback_plan(task_text: str) -> tuple[str, list[Subtask]]:
    first_line = next((line.strip() for line in task_text.splitlines() if line.strip()), "Complete the task")
    summary = first_line[:160]
    subtask = Subtask(
        id="implement_task",
        title="Implement the requested task",
        description=summary,
        status="todo",
        attempts=0,
        acceptance_criteria=[
            "The requested deliverable is implemented.",
            "Project checks pass.",
            "The result matches the task requirements.",
        ],
    )
    return summary, [subtask]


def parse_task_plan(text: str, task_text: str = "") -> tuple[str, list[Subtask]]:
    try:
        data = _load_json_object(text)
    except Exception:
        if task_text:
            return _build_fallback_plan(task_text)
        raise

    summary = str(data.get("summary", "")).strip()
    raw_subtasks = data.get("subtasks", [])

    if not isinstance(raw_subtasks, list) or not raw_subtasks:
        raise ValueError("Task plan must define a non-empty subtasks array")

    subtasks: list[Subtask] = []
    for index, item in enumerate(raw_subtasks, start=1):
        if not isinstance(item, dict):
            raise ValueError("Each subtask must be an object")

        subtask_id = str(item.get("id", "")).strip() or f"subtask_{index}"
        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()
        acceptance = item.get("acceptance_criteria", [])

        if not title:
            raise ValueError("Each subtask must define a non-empty title")

        if not isinstance(acceptance, list) or not all(
            isinstance(point, str) and point.strip() for point in acceptance
        ):
            raise ValueError("acceptance_criteria must be a list of non-empty strings")

        subtasks.append(
            Subtask(
                id=subtask_id,
                title=title,
                description=description,
                status="todo",
                attempts=0,
                acceptance_criteria=acceptance,
            )
        )

    return summary, subtasks


def parse_subtask_selection(text: str) -> tuple[str, str]:
    data = _load_json_object(text)
    subtask_id = str(data.get("subtask_id", "")).strip()
    reason = str(data.get("reason", "")).strip()

    if not subtask_id:
        raise ValueError("Subtask selection must define subtask_id")

    return subtask_id, reason


def parse_task_selection(text: str) -> tuple[str, str]:
    data = _load_json_object(text)
    task_file = str(data.get("task_file", "")).strip()
    reason = str(data.get("reason", "")).strip()

    if not task_file:
        raise ValueError("Task selection must define task_file")

    return task_file, reason


def parse_failure_decision(text: str, allowed_decisions: list[str]) -> tuple[str, str]:
    data = _load_json_object(text)
    decision = str(data.get("decision", "")).strip()
    reason = str(data.get("reason", "")).strip()

    if decision not in allowed_decisions:
        raise ValueError(
            "Failure decision must be one of: " + ", ".join(allowed_decisions)
        )

    return decision, reason
