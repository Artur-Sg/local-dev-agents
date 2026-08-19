import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DEFAULT_MODEL_API_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL_NAME = "qwen2.5-coder:7b"
DEFAULT_AGENT_MAX_ATTEMPTS = 5
DEFAULT_AGENT_HTTP_TIMEOUT = 180
DEFAULT_NARRATOR_USE_MODEL = False

_ENV_LOADED = False


def load_env() -> None:
    global _ENV_LOADED

    if _ENV_LOADED:
        return

    _ENV_LOADED = True

    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def get_env(name: str, default: str) -> str:
    load_env()
    return os.environ.get(name, default)


def get_env_int(name: str, default: int) -> int:
    value = get_env(name, str(default))

    try:
        return int(value)
    except ValueError:
        return default


def get_env_bool(name: str, default: bool) -> bool:
    value = get_env(name, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def get_model_api_url() -> str:
    return get_env("MODEL_API_URL", DEFAULT_MODEL_API_URL)


def get_default_model_name() -> str:
    return get_env("MODEL_DEFAULT_NAME", DEFAULT_MODEL_NAME)


def get_agent_http_timeout() -> int:
    return get_env_int("AGENT_HTTP_TIMEOUT", DEFAULT_AGENT_HTTP_TIMEOUT)


def get_agent_max_attempts() -> int:
    return get_env_int("AGENT_MAX_ATTEMPTS", DEFAULT_AGENT_MAX_ATTEMPTS)


def get_narrator_use_model() -> bool:
    return get_env_bool("NARRATOR_USE_MODEL", DEFAULT_NARRATOR_USE_MODEL)
