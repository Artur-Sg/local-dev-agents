import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG_PATH = ROOT / "config" / "project.json"


def load_project_config() -> dict:
    if not PROJECT_CONFIG_PATH.exists():
        return {
            "profile": "python",
            "sandbox_dir": "sandboxes/test-fastapi",
        }

    return json.loads(PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))


def get_profile() -> str:
    config = load_project_config()
    return config.get("profile", "python")


def get_sandbox_dir() -> Path:
    config = load_project_config()
    sandbox_dir = config.get("sandbox_dir", "sandboxes/test-fastapi")
    path = ROOT / sandbox_dir

    resolved_root = ROOT.resolve()
    resolved_path = path.resolve()

    if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
        raise ValueError(f"Sandbox dir escapes project root: {sandbox_dir}")

    return path
