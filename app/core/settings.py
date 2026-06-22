import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "config" / "project.json"


def load_project_config() -> dict:
    if not PROJECT_CONFIG_PATH.exists():
        return {
            "profile": "python",
            "sandbox_dir": "sandboxes/test-fastapi",
            "project_dir": ".",
            "test_runner": {
                "type": "docker",
                "image": "local-dev-agent-python:3.12",
                "command": ["pytest", "-q"],
            },
            "allowed_write_paths": [],
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


def get_project_dir() -> Path:
    config = load_project_config()
    project_dir = config.get("project_dir", ".")

    if not isinstance(project_dir, str) or not project_dir.strip():
        raise ValueError("project_dir must be a non-empty string")

    path = get_sandbox_dir() / project_dir
    resolved_sandbox = get_sandbox_dir().resolve()
    resolved_path = path.resolve()

    if resolved_path != resolved_sandbox and resolved_sandbox not in resolved_path.parents:
        raise ValueError(f"Project dir escapes sandbox root: {project_dir}")

    return path


def get_allowed_write_paths() -> list[str]:
    config = load_project_config()
    allowed_paths = config.get("allowed_write_paths", [])

    if not isinstance(allowed_paths, list) or not all(
        isinstance(path, str) and path.strip() for path in allowed_paths
    ):
        raise ValueError("allowed_write_paths must be a list of non-empty strings")

    return allowed_paths


def get_test_runner() -> dict:
    config = load_project_config()
    test_runner = config.get("test_runner", {})

    if not isinstance(test_runner, dict):
        raise ValueError("test_runner must be an object")

    runner_type = test_runner.get("type", "")
    image = test_runner.get("image", "")
    command = test_runner.get("command", [])

    if runner_type != "docker":
        raise ValueError(f"Unsupported test_runner type: {runner_type}")

    if not isinstance(image, str) or not image.strip():
        raise ValueError("test_runner.image must be a non-empty string")

    if not isinstance(command, list) or not all(
        isinstance(part, str) and part.strip() for part in command
    ):
        raise ValueError("test_runner.command must be a list of non-empty strings")

    return {
        "type": runner_type,
        "image": image,
        "command": command,
    }
