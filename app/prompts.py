import json

from settings import ROOT

PROMPTS_CONFIG_PATH = ROOT / "config" / "prompts.json"


def load_prompts_config() -> dict:
    if not PROMPTS_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing prompts config: {PROMPTS_CONFIG_PATH}")

    return json.loads(PROMPTS_CONFIG_PATH.read_text(encoding="utf-8"))


def get_prompt_template(name: str) -> str:
    config = load_prompts_config()
    template = config.get(name)

    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"Missing or invalid prompt template: {name}")

    return template


def render_prompt(name: str, **values: str) -> str:
    template = get_prompt_template(name)
    return template.format(**values).strip()
