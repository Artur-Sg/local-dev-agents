from dataclasses import dataclass
from pathlib import Path
import re

from core.actions import RUN_VISUAL_CHECK
from core.roles import require_action
from core.settings import get_project_dir
from core.verification_plan import get_active_visual_review


@dataclass(frozen=True)
class VisualCheckResult:
    skipped: bool
    passed: bool
    summary: str
    details: list[str]
    metrics: dict[str, object]


def run_visual_check() -> VisualCheckResult:
    require_action(RUN_VISUAL_CHECK)

    project_dir = get_project_dir()
    config = get_active_visual_review()
    enabled = config["enabled"]
    rules = config["rules"]

    metrics: dict[str, object] = {
        "enabled": enabled,
        "files": config["files"],
        "rule_count": len(rules),
        "project_dir": str(project_dir),
    }

    if not enabled:
        return VisualCheckResult(
            skipped=True,
            passed=True,
            summary="Visual QA отключён для текущей задачи.",
            details=[],
            metrics=metrics,
        )

    details: list[str] = []
    file_cache: dict[str, str] = {}
    missing_files = [
        rel_path
        for rel_path in config["files"]
        if not (project_dir / rel_path).exists()
    ]

    if missing_files:
        return VisualCheckResult(
            skipped=False,
            passed=False,
            summary=config["failure_summary"] or "Визуальная проверка не пройдена.",
            details=[f"Не найден обязательный файл visual QA: {rel_path}" for rel_path in missing_files],
            metrics=metrics,
        )

    for rule in rules:
        error = _evaluate_rule(project_dir, file_cache, rule, metrics)
        if error is not None:
            details.append(error)

    passed = not details
    summary = config["success_summary"] if passed else config["failure_summary"]
    if not summary:
        summary = (
            "Визуальная проверка пройдена."
            if passed
            else "Визуальная проверка не пройдена."
        )

    return VisualCheckResult(
        skipped=False,
        passed=passed,
        summary=summary,
        details=details,
        metrics=metrics,
    )


def _evaluate_rule(
    project_dir: Path,
    file_cache: dict[str, str],
    rule: dict[str, object],
    metrics: dict[str, object],
) -> str | None:
    if not isinstance(rule, dict):
        raise ValueError("visual_review rule must be an object")

    rule_type = str(rule.get("type", "")).strip()
    label = str(rule.get("label", rule_type)).strip() or rule_type
    metrics_key = str(rule.get("metric", label)).strip() or label
    message = str(rule.get("message", f"Visual rule failed: {label}")).strip()

    if rule_type == "file_exists":
        rel_path = _get_rule_path(rule)
        path = project_dir / rel_path
        result = path.exists()
        metrics[metrics_key] = result
        return None if result else message

    rel_path = _get_rule_path(rule)
    content = _read_project_file(project_dir, rel_path, file_cache)

    if rule_type == "contains":
        needle = _get_rule_string(rule, "value")
        result = needle in content
        metrics[metrics_key] = result
        return None if result else message

    if rule_type == "not_contains":
        needle = _get_rule_string(rule, "value")
        result = needle not in content
        metrics[metrics_key] = result
        return None if result else message

    if rule_type == "regex":
        pattern = _get_rule_string(rule, "pattern")
        result = re.search(pattern, content) is not None
        metrics[metrics_key] = result
        return None if result else message

    if rule_type == "regex_count_at_least":
        pattern = _get_rule_string(rule, "pattern")
        min_count = _get_rule_int(rule, "min")
        count = len(re.findall(pattern, content))
        metrics[metrics_key] = count
        return None if count >= min_count else message

    if rule_type == "regex_count_at_most":
        pattern = _get_rule_string(rule, "pattern")
        max_count = _get_rule_int(rule, "max")
        count = len(re.findall(pattern, content))
        metrics[metrics_key] = count
        return None if count <= max_count else message

    raise ValueError(f"Unsupported visual_review rule type: {rule_type}")


def _get_rule_path(rule: dict[str, object]) -> str:
    path = rule.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("visual_review rule path must be a non-empty string")
    return path.strip()


def _get_rule_string(rule: dict[str, object], key: str) -> str:
    value = rule.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"visual_review rule {key} must be a non-empty string")
    return value


def _get_rule_int(rule: dict[str, object], key: str) -> int:
    value = rule.get(key)
    if not isinstance(value, int):
        raise ValueError(f"visual_review rule {key} must be an integer")
    return value


def _read_project_file(project_dir: Path, rel_path: str, file_cache: dict[str, str]) -> str:
    if rel_path not in file_cache:
        path = project_dir / rel_path
        if not path.exists():
            raise FileNotFoundError(f"Visual QA file not found: {path}")
        file_cache[rel_path] = path.read_text(encoding="utf-8")
    return file_cache[rel_path]
