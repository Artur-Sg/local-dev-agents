import json
from pathlib import Path

from core.runtime import get_current_capability, get_current_role
from core.settings import ROOT

ROLES_CONFIG_PATH = ROOT / "config" / "roles.json"
ACTORS_CONFIG_PATH = ROOT / "config" / "actors.json"


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def load_roles_config() -> dict:
    return _read_json(ROLES_CONFIG_PATH)


def load_actors_config() -> dict:
    return _read_json(ACTORS_CONFIG_PATH)


def get_default_language() -> str:
    language = load_actors_config().get("default_language", "ru")

    if not isinstance(language, str) or not language.strip():
        raise ValueError("actors.json must define a non-empty default_language")

    return language


def get_default_model() -> str:
    default_model = load_roles_config().get("default_model")

    if not isinstance(default_model, str) or not default_model.strip():
        raise ValueError("roles.json must define a non-empty default_model")

    return default_model


def get_actor_config(actor: str) -> dict:
    actors = load_actors_config().get("actors", {})
    actor_config = actors.get(actor)

    if actor_config is None:
        raise ValueError(f"Unknown actor: {actor}")

    display_name = actor_config.get("display_name", "").strip()
    emoji = actor_config.get("emoji", "").strip()

    if not display_name:
        raise ValueError(f"Actor {actor} has empty display_name")

    return {
        "display_name": display_name,
        "emoji": emoji,
        "voice": actor_config.get("voice", "").strip(),
        "communication_prompt": actor_config.get("communication_prompt", "").strip(),
    }


def get_role_config(role: str) -> dict:
    roles = load_roles_config().get("roles", {})
    role_config = roles.get(role)

    if role_config is None:
        raise ValueError(f"Unknown role: {role}")

    actor = role_config.get("actor", "").strip()
    persona_prompt = role_config.get("persona_prompt", "").strip()
    allowed_actions = role_config.get("allowed_actions", [])
    capabilities = role_config.get("capabilities", {})
    model = role_config.get("model")

    if not actor:
        raise ValueError(f"Role {role} must define actor")

    get_actor_config(actor)

    if not isinstance(allowed_actions, list) or not all(
        isinstance(action, str) and action for action in allowed_actions
    ):
        raise ValueError(f"Role {role} has invalid allowed_actions")

    if not isinstance(capabilities, dict) or not capabilities:
        raise ValueError(f"Role {role} must define capabilities")

    capability_uses_model = any(
        "call_model" in capability.get("actions", []) for capability in capabilities.values()
    )

    if model is None and capability_uses_model:
        model = get_default_model()

    return {
        "actor": actor,
        "model": model,
        "persona_prompt": persona_prompt,
        "allowed_actions": allowed_actions,
        "capabilities": capabilities,
    }


def get_capability_config(role: str, capability: str) -> dict:
    role_config = get_role_config(role)
    capability_config = role_config["capabilities"].get(capability)

    if capability_config is None:
        raise ValueError(f"Role {role} does not define capability {capability}")

    actions = capability_config.get("actions", [])
    prompt = capability_config.get("prompt", "").strip()

    if not isinstance(actions, list) or not all(isinstance(action, str) and action for action in actions):
        raise ValueError(f"Role {role} capability {capability} has invalid actions")

    for action in actions:
        if action not in role_config["allowed_actions"]:
            raise ValueError(
                f"Role {role} capability {capability} uses action {action} outside allowed_actions"
            )

    return {
        "prompt": prompt,
        "actions": actions,
    }


def has_action(role: str, action: str, capability: str | None = None) -> bool:
    role_config = get_role_config(role)

    if action not in role_config["allowed_actions"]:
        return False

    if capability is None:
        return True

    capability_config = get_capability_config(role, capability)
    return action in capability_config["actions"]


def require_role_action(role: str, action: str, capability: str | None = None) -> None:
    if not has_action(role, action, capability):
        suffix = f" with capability {capability}" if capability else ""
        raise PermissionError(f"Role {role}{suffix} is not allowed to perform action {action}")


def require_action(action: str) -> None:
    role = get_current_role()
    capability = get_current_capability()
    require_role_action(role, action, capability)


def _read_prompt_file(path_str: str) -> str:
    if not path_str:
        return ""

    path = ROOT / "config" / path_str
    if not path.exists():
        raise FileNotFoundError(f"Missing role prompt: {path}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Empty role prompt: {path}")

    return content


def read_config_prompt(path_str: str) -> str:
    return _read_prompt_file(path_str)


def build_system_prompt(role: str, capability: str) -> str:
    role_config = get_role_config(role)
    capability_config = get_capability_config(role, capability)

    parts = []

    persona = _read_prompt_file(role_config["persona_prompt"])
    if persona:
        parts.append(persona)

    capability_prompt = _read_prompt_file(capability_config["prompt"])
    if capability_prompt:
        parts.append(capability_prompt)

    prompt = "\n\n".join(parts).strip()
    if not prompt:
        raise ValueError(f"Role {role} capability {capability} produced empty system prompt")

    return prompt
