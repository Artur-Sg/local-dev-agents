import json

from runtime import get_current_role
from settings import ROOT

ROLES_CONFIG_PATH = ROOT / "config" / "roles.json"


def load_roles_config() -> dict:
    if not ROLES_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing roles config: {ROLES_CONFIG_PATH}")

    return json.loads(ROLES_CONFIG_PATH.read_text(encoding="utf-8"))


def get_default_model() -> str:
    config = load_roles_config()
    default_model = config.get("default_model")

    if not isinstance(default_model, str) or not default_model.strip():
        raise ValueError("roles.json must define a non-empty default_model")

    return default_model


def get_role_config(role: str) -> dict:
    config = load_roles_config()
    roles = config.get("roles", {})
    role_config = roles.get(role)

    if role_config is None:
        raise ValueError(f"Unknown role: {role}")

    model = role_config.get("model")
    system_prompt = role_config.get("system_prompt", "").strip()
    allowed_actions = role_config.get("allowed_actions", [])

    if not system_prompt:
        raise ValueError(f"Role {role} has empty system_prompt")

    if model is None and role not in {"tester", "committer", "telegram_user"}:
        model = get_default_model()

    if not isinstance(allowed_actions, list) or not all(
        isinstance(action, str) and action for action in allowed_actions
    ):
        raise ValueError(f"Role {role} has invalid allowed_actions")

    return {
        "model": model,
        "system_prompt": system_prompt,
        "allowed_actions": allowed_actions,
    }


def has_action(role: str, action: str) -> bool:
    role_config = get_role_config(role)
    return action in role_config["allowed_actions"]


def require_action(action: str) -> None:
    role = get_current_role()

    if not has_action(role, action):
        raise PermissionError(f"Role {role} is not allowed to perform action {action}")
