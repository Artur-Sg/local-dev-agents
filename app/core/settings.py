import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RUNTIME_PROJECT_CONFIG_PATH = DATA_DIR / "project.runtime.json"


def load_project_config() -> dict:
    if not RUNTIME_PROJECT_CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Missing runtime project config: data/project.runtime.json. "
            "Run `./agent.sh kickoff` first."
        )

    config = json.loads(RUNTIME_PROJECT_CONFIG_PATH.read_text(encoding="utf-8"))

    if not isinstance(config, dict):
        raise ValueError("project runtime config must be a JSON object")

    return config


def get_stack_id() -> str:
    config = load_project_config()
    stack = config.get("stack", {})
    stack_id = stack.get("id", "")

    if not isinstance(stack_id, str) or not stack_id.strip():
        raise ValueError("stack.id must be a non-empty string")

    return stack_id.strip()


def load_stack_config() -> dict:
    config = load_project_config()
    stack = config.get("stack", {})

    if not isinstance(stack, dict) or not stack:
        raise ValueError("project config must define a non-empty stack object")

    return stack


def load_verification_config() -> dict:
    config = load_project_config()
    verification = config.get("verification", {})

    if not isinstance(verification, dict):
        raise ValueError("project config must define verification as an object")

    return verification


def get_sandbox_dir() -> Path:
    project_dir = get_project_dir()
    path = project_dir.parent

    resolved_root = ROOT.resolve()
    resolved_path = path.resolve()

    if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
        raise ValueError(f"Sandbox dir escapes project root: {path}")

    return path


def get_project_dir() -> Path:
    config = load_project_config()
    project = config.get("project", {})
    project_path = project.get("path", "")

    if not isinstance(project_path, str) or not project_path.strip():
        raise ValueError("project.path must be a non-empty string")

    path = ROOT / project_path
    resolved_root = ROOT.resolve()
    resolved_path = path.resolve()

    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"Project path escapes project root: {project_path}")

    return path


def get_allowed_write_paths() -> list[str]:
    config = load_stack_config()
    workspace = config.get("workspace", {})
    allowed_paths = workspace.get("allowed_write_paths", [])

    if not isinstance(allowed_paths, list) or not all(
        isinstance(path, str) and path.strip() for path in allowed_paths
    ):
        raise ValueError("allowed_write_paths must be a list of non-empty strings")

    return allowed_paths


def get_test_runner() -> dict:
    config = load_stack_config()
    test_runner = config.get("runner", {})

    if not isinstance(test_runner, dict):
        raise ValueError("stack.runner must be an object")

    runner_type = str(test_runner.get("type", "")).strip()
    image = str(test_runner.get("image", "")).strip()
    command = test_runner.get("command", [])
    setup_commands = test_runner.get("setup_commands", [])

    if not runner_type:
        raise ValueError("test_runner.type must be a non-empty string")

    if not isinstance(command, list) or not all(
        isinstance(part, str) and part.strip() for part in command
    ):
        raise ValueError("test_runner.command must be a list of non-empty strings")

    if not isinstance(setup_commands, list) or not all(
        isinstance(part, str) and part.strip() for part in setup_commands
    ):
        raise ValueError("test_runner.setup_commands must be a list of non-empty strings")

    if runner_type == "docker":
        if not image:
            raise ValueError("test_runner.image must be a non-empty string for docker runner")
    elif runner_type == "local":
        if image:
            raise ValueError("test_runner.image is not used for local runner")
    else:
        raise ValueError(f"Unsupported test_runner type: {runner_type}")

    return {
        "type": runner_type,
        "image": image,
        "setup_commands": setup_commands,
        "command": command,
    }


def get_visual_review_config() -> dict:
    config = load_verification_config()
    visual_review = config.get("visual_review", {})

    if not isinstance(visual_review, dict):
        raise ValueError("visual_review must be an object")

    enabled = visual_review.get("enabled", False)
    files = visual_review.get("files", [])
    prompt = visual_review.get("prompt", "").strip()
    prompt_text = visual_review.get("prompt_text", "").strip()
    rules = visual_review.get("rules", [])
    success_summary = visual_review.get("success_summary", "").strip()
    failure_summary = visual_review.get("failure_summary", "").strip()

    if not isinstance(enabled, bool):
        raise ValueError("visual_review.enabled must be a boolean")

    if not isinstance(files, list) or not all(
        isinstance(path, str) and path.strip() for path in files
    ):
        raise ValueError("visual_review.files must be a list of non-empty strings")

    if not isinstance(rules, list):
        raise ValueError("visual_review.rules must be a list")

    return {
        "enabled": enabled,
        "files": files,
        "prompt": prompt,
        "prompt_text": prompt_text,
        "rules": rules,
        "success_summary": success_summary,
        "failure_summary": failure_summary,
    }
