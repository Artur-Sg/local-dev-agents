from copy import deepcopy

from core.runtime import peek_current_run_id
from core.run_repository import find_session
from core.settings import (
    get_allowed_write_paths,
    get_test_runner,
    get_visual_review_config,
    load_verification_config,
)


def build_verification_plan() -> dict[str, object]:
    verification = load_verification_config()
    visual_review = get_visual_review_config()
    runner = get_test_runner()

    trusted_paths = _normalize_string_list(verification.get("trusted_paths", []))
    protected_paths = _normalize_string_list(verification.get("must_not_modify", []))
    allowed_write_paths = get_allowed_write_paths()

    return {
        "strategy": str(verification.get("strategy", "task-driven")).strip() or "task-driven",
        "allowed_write_paths": allowed_write_paths,
        "trusted_paths": trusted_paths,
        "protected_paths": protected_paths,
        "checks": {
            "tests": {
                "enabled": True,
                "runner_type": runner["type"],
                "image": runner["image"],
                "setup_commands": runner["setup_commands"],
                "command": runner["command"],
            },
            "visual_review": {
                **visual_review,
            },
        },
        "incremental_policy": {
            "mode": "modify_in_place",
            "preserve_existing_project": True,
            "preserve_unrelated_files": True,
            "avoid_unrelated_rewrites": True,
            "write_only_allowed_paths": True,
        },
    }


def get_verification_plan_text(plan: dict[str, object]) -> str:
    checks = plan.get("checks", {})
    tests = checks.get("tests", {}) if isinstance(checks, dict) else {}
    visual_review = checks.get("visual_review", {}) if isinstance(checks, dict) else {}

    lines = [
        "Verification plan:",
        f"- strategy: {plan.get('strategy', 'task-driven')}",
        "- checks:",
        f"  - tests: {'enabled' if tests.get('enabled') else 'disabled'}",
        f"  - visual review: {'enabled' if visual_review.get('enabled') else 'disabled'}",
    ]

    trusted_paths = _normalize_string_list(plan.get("trusted_paths", []))
    if trusted_paths:
        lines.append("- trusted verification files:")
        lines.extend(f"  - {path}" for path in trusted_paths)

    protected_paths = _normalize_string_list(plan.get("protected_paths", []))
    if protected_paths:
        lines.append("- protected files:")
        lines.extend(f"  - {path}" for path in protected_paths)

    return "\n".join(lines)


def get_active_verification_plan() -> dict[str, object]:
    run_id = peek_current_run_id()
    if run_id:
        session = find_session(run_id)
        if session is not None:
            plan = session.artifacts.get("verification_plan")
            if isinstance(plan, dict) and plan:
                return deepcopy(plan)

    return build_verification_plan()


def get_active_test_runner() -> dict[str, object]:
    plan = get_active_verification_plan()
    checks = plan.get("checks", {})
    tests = checks.get("tests", {}) if isinstance(checks, dict) else {}

    return {
        "type": str(tests.get("runner_type", "")).strip(),
        "image": str(tests.get("image", "")).strip(),
        "setup_commands": _normalize_string_list(tests.get("setup_commands", [])),
        "command": _normalize_string_list(tests.get("command", [])),
    }


def get_active_visual_review() -> dict[str, object]:
    plan = get_active_verification_plan()
    checks = plan.get("checks", {})
    visual_review = checks.get("visual_review", {}) if isinstance(checks, dict) else {}

    return {
        "enabled": bool(visual_review.get("enabled", False)),
        "files": _normalize_string_list(visual_review.get("files", [])),
        "prompt": str(visual_review.get("prompt", "")).strip(),
        "prompt_text": str(visual_review.get("prompt_text", "")).strip(),
        "rules": visual_review.get("rules", []),
        "success_summary": str(visual_review.get("success_summary", "")).strip(),
        "failure_summary": str(visual_review.get("failure_summary", "")).strip(),
    }


def get_incremental_rules_text(plan: dict[str, object]) -> str:
    protected_paths = _normalize_string_list(plan.get("protected_paths", []))

    lines = [
        "- Continue from the existing project state.",
        "- Modify files in place instead of rebuilding the project from scratch.",
        "- Preserve working structure and keep unrelated files intact.",
        "- Prefer the smallest coherent diff that moves the task forward.",
        "- Write only to allowed output paths.",
    ]

    if protected_paths:
        lines.append("- Do not modify protected verification files:")
        lines.extend(f"  - {path}" for path in protected_paths)

    return "\n".join(lines)


def _normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
