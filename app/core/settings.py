import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG_PATH = ROOT / "config" / "project.json"
PROFILES_DIR = ROOT / "config" / "profiles"


def load_project_config() -> dict:
    if not PROJECT_CONFIG_PATH.exists():
        return {
            "profile": "static-html",
            "sandbox_dir": "sandboxes",
            "project_dir": "static-bakery",
        }

    return json.loads(PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))


def get_profile() -> str:
    config = load_project_config()
    return config.get("profile", "static-html")


def load_profile_config() -> dict:
    profile = get_profile()
    profile_path = PROFILES_DIR / f"{profile}.json"

    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile config: {profile_path}")

    return json.loads(profile_path.read_text(encoding="utf-8"))


def get_sandbox_dir() -> Path:
    config = load_project_config()
    sandbox_dir = config.get("sandbox_dir", "sandboxes")
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
    config = load_profile_config()
    allowed_paths = config.get("allowed_write_paths", [])

    if not isinstance(allowed_paths, list) or not all(
        isinstance(path, str) and path.strip() for path in allowed_paths
    ):
        raise ValueError("allowed_write_paths must be a list of non-empty strings")

    return allowed_paths


def get_test_runner() -> dict:
    config = load_profile_config()
    test_runner = config.get("test_runner", {})

    if not isinstance(test_runner, dict):
        raise ValueError("test_runner must be an object")

    runner_type = test_runner.get("type", "")
    image = test_runner.get("image", "")
    command = test_runner.get("command", [])
    setup_commands = test_runner.get("setup_commands", [])

    if runner_type != "docker":
        raise ValueError(f"Unsupported test_runner type: {runner_type}")

    if not isinstance(image, str) or not image.strip():
        raise ValueError("test_runner.image must be a non-empty string")

    if not isinstance(command, list) or not all(
        isinstance(part, str) and part.strip() for part in command
    ):
        raise ValueError("test_runner.command must be a list of non-empty strings")

    if not isinstance(setup_commands, list) or not all(
        isinstance(part, str) and part.strip() for part in setup_commands
    ):
        raise ValueError("test_runner.setup_commands must be a list of non-empty strings")

    return {
        "type": runner_type,
        "image": image,
        "setup_commands": setup_commands,
        "command": command,
    }


def get_task_overlay_path() -> Path | None:
    config = load_profile_config()
    task_overlay = config.get("task_overlay", "").strip()

    if not task_overlay:
        return None

    path = ROOT / task_overlay
    if not path.exists():
        raise FileNotFoundError(f"Missing task overlay: {path}")

    return path


def get_visual_review_config() -> dict:
    config = load_profile_config()
    visual_review = config.get("visual_review", {})

    if not isinstance(visual_review, dict):
        raise ValueError("visual_review must be an object")

    enabled = visual_review.get("enabled", False)
    checker = visual_review.get("checker", "").strip()
    files = visual_review.get("files", [])
    prompt = visual_review.get("prompt", "").strip()

    if not isinstance(enabled, bool):
        raise ValueError("visual_review.enabled must be a boolean")

    if not isinstance(files, list) or not all(
        isinstance(path, str) and path.strip() for path in files
    ):
        raise ValueError("visual_review.files must be a list of non-empty strings")

    return {
        "enabled": enabled,
        "checker": checker,
        "files": files,
        "prompt": prompt,
    }
