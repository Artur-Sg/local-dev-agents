from pathlib import Path

from core.settings import ROOT

PROMPTS_DIR = ROOT / "config" / "prompts"


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def get_prompt_path(name: str) -> Path:
    path = PROMPTS_DIR / f"{name}.md"

    if not path.exists():
        raise FileNotFoundError(f"Missing prompt template: {path}")

    return path


def get_prompt_template(name: str) -> str:
    template = get_prompt_path(name).read_text(encoding="utf-8")

    if not template.strip():
        raise ValueError(f"Missing or invalid prompt template: {name}")

    return template


def render_prompt(name: str, **values: str) -> str:
    template = get_prompt_template(name)
    return template.format_map(_SafeFormatDict(values)).strip()
