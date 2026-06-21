import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
DEFAULT_AGENT_MAX_ATTEMPTS = 5
DEFAULT_AGENT_HTTP_TIMEOUT = 180

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


def get_ollama_url() -> str:
    return get_env("OLLAMA_URL", DEFAULT_OLLAMA_URL)


def get_ollama_model() -> str:
    return get_env("OLLAMA_DEFAULT_MODEL", DEFAULT_OLLAMA_MODEL)


def get_agent_http_timeout() -> int:
    return get_env_int("AGENT_HTTP_TIMEOUT", DEFAULT_AGENT_HTTP_TIMEOUT)


def get_agent_max_attempts() -> int:
    return get_env_int("AGENT_MAX_ATTEMPTS", DEFAULT_AGENT_MAX_ATTEMPTS)
