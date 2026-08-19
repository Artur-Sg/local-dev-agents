import json
import re
import subprocess
import shutil
from pathlib import Path

from core.db import init_db, reset_runs_table, reset_tasks_table, upsert_task_record
from task_repository import sync_task_record_to_file

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "runs"
INTAKE_PATH = CONFIG_DIR / "intake.json"
RUNTIME_PROJECT_CONFIG_PATH = DATA_DIR / "project.runtime.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "task"


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _apply_stack_bootstrap_files(stack_config: dict, project_dir: Path) -> None:
    bootstrap_files = stack_config.get("bootstrap_files", [])
    if not bootstrap_files:
        return

    if not isinstance(bootstrap_files, list):
        raise ValueError("stack bootstrap_files must be a list")

    for item in bootstrap_files:
        if not isinstance(item, dict):
            raise ValueError("stack bootstrap_files entries must be objects")

        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        content = item.get("content")
        if not target:
            raise ValueError("stack bootstrap_files entries must define target")
        if bool(source) == bool(content):
            raise ValueError("stack bootstrap_files entries must define exactly one of source or content")

        target_path = project_dir / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source:
            source_path = ROOT / source
            if not source_path.exists():
                raise FileNotFoundError(f"Missing bootstrap source: {source_path}")
            shutil.copyfile(source_path, target_path)
            continue

        if not isinstance(content, str):
            raise ValueError("stack bootstrap_files content must be a string")

        target_path.write_text(content, encoding="utf-8")


def _clear_task_queues() -> None:
    reset_tasks_table()
    for group in ("inbox", "blocked", "needs-human", "done"):
        directory = TASKS_DIR / group
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.glob("*.md"):
            if path.name == ".gitkeep":
                continue
            path.unlink()


def _clear_runs() -> None:
    reset_runs_table()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    for path in RUNS_DIR.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            import shutil
            shutil.rmtree(path)
        else:
            path.unlink()


def _ensure_project_gitignore(project_dir: Path) -> None:
    gitignore = project_dir / ".gitignore"
    if gitignore.exists():
        return
    gitignore.write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")


def _reset_project_dir(project_dir: Path, mode: str) -> None:
    project_dir.parent.mkdir(parents=True, exist_ok=True)

    if mode == "preserve":
        project_dir.mkdir(parents=True, exist_ok=True)
        return

    if mode == "recreate":
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        return

    if mode == "git_restore":
        if not project_dir.exists():
            project_dir.mkdir(parents=True, exist_ok=True)
            return
        if not (project_dir / ".git").exists():
            import shutil
            shutil.rmtree(project_dir)
            project_dir.mkdir(parents=True, exist_ok=True)
            return

        subprocess.run(
            ["git", "restore", "--source=HEAD", "--staged", "--worktree", "."],
            cwd=project_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=project_dir,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return

    raise ValueError(f"Unsupported project_reset mode: {mode}")


def _init_project_git(project_dir: Path) -> None:
    if (project_dir / ".git").exists():
        return

    subprocess.run(
        ["git", "init"],
        cwd=project_dir,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _project_has_git_head(project_dir: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode == 0


def _project_has_uncommitted_changes(project_dir: Path) -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )
    return bool(proc.stdout.strip())


def _commit_initial_project_baseline(project_dir: Path) -> None:
    if _project_has_git_head(project_dir):
        return

    if not _project_has_uncommitted_changes(project_dir):
        return

    subprocess.run(
        ["git", "add", "."],
        cwd=project_dir,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=local-dev-agent",
            "-c",
            "user.email=local-dev-agent@local",
            "commit",
            "-m",
            "Initialize sandbox baseline",
        ],
        cwd=project_dir,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _render_task_markdown(task_config: dict, verification_config: dict) -> str:
    description = str(task_config.get("description", "")).strip()
    if not description:
        raise ValueError("task.description must be a non-empty string")

    lines = [description]

    constraints = task_config.get("constraints", [])
    if constraints:
        lines.extend(["", "Constraints:"])
        lines.extend(f"- {item}" for item in constraints)

    done_when = task_config.get("done_when", [])
    if done_when:
        lines.extend(["", "Done when:"])
        lines.extend(f"- {item}" for item in done_when)

    lines.extend(
        [
            "",
            "Execution policy:",
            "- Continue from the current project state.",
            "- Modify the project in place instead of replacing it with a new layout.",
            "- Keep unrelated files and working structure intact.",
            "- Only change files that are necessary for the current increment.",
        ]
    )

    trusted_paths = verification_config.get("trusted_paths", [])
    if trusted_paths:
        lines.extend(["", "Trusted verification files:"])
        lines.extend(f"- {item}" for item in trusted_paths)

    must_not_modify = verification_config.get("must_not_modify", [])
    if must_not_modify:
        lines.extend(["", "Do not modify:"])
        lines.extend(f"- {item}" for item in must_not_modify)

    return "\n".join(lines).strip()
def main() -> None:
    init_db()
    intake = _load_json(INTAKE_PATH)

    run_config = intake.get("run", {})
    project_config = intake.get("project", {})
    stack_config = intake.get("stack", {})
    task_config = intake.get("task", {})
    verification_config = intake.get("verification", {})

    if not isinstance(run_config, dict):
        raise ValueError("intake.run must be an object")
    if not isinstance(project_config, dict):
        raise ValueError("intake.project must be an object")
    if not isinstance(stack_config, dict):
        raise ValueError("intake.stack must be an object")
    if not isinstance(task_config, dict):
        raise ValueError("intake.task must be an object")
    if not isinstance(verification_config, dict):
        raise ValueError("intake.verification must be an object")

    project_name = str(project_config.get("name", "")).strip()
    project_path = str(project_config.get("path", "")).strip() or f"sandboxes/{_slugify(project_name)}"
    stack_id = str(stack_config.get("id", "")).strip()
    start_mode = str(run_config.get("mode", "prepare")).strip() or "prepare"
    project_reset = str(run_config.get("project_reset", "preserve")).strip() or "preserve"
    reset_tasks = bool(run_config.get("reset_tasks", True))
    reset_runs = bool(run_config.get("reset_runs", True))
    init_git = bool(run_config.get("init_git", True))

    if not project_name:
        raise ValueError("project.name must be a non-empty string")
    if not project_path:
        raise ValueError("project.path must be a non-empty string")
    if not stack_id:
        raise ValueError("stack.id must be a non-empty string")

    normalized_project = {
        **project_config,
        "name": project_name,
        "path": project_path,
    }

    task_markdown = _render_task_markdown(task_config, verification_config)
    project_dir = ROOT / project_path

    if reset_tasks:
        _clear_task_queues()
    if reset_runs:
        _clear_runs()

    _reset_project_dir(project_dir, project_reset)
    _ensure_project_gitignore(project_dir)
    if init_git:
        _init_project_git(project_dir)
    _apply_stack_bootstrap_files(stack_config, project_dir)
    if init_git:
        _commit_initial_project_baseline(project_dir)

    _write_json(
        RUNTIME_PROJECT_CONFIG_PATH,
        {
            "_meta": {
                "generated": True,
                "generated_by": "kickoff",
                "description": "Generated runtime project config. Edit config/intake.json instead.",
            },
            "project": normalized_project,
            "stack": stack_config,
            "verification": verification_config,
        },
    )

    task_id = str(task_config.get("id", "")).strip() or _slugify(project_name)
    task_relpath = f"tasks/inbox/{task_id}.md"
    task_title = str(task_config.get("title", "")).strip() or project_name
    task_priority = str(task_config.get("priority", "normal")).strip() or "normal"
    task_kind = str(task_config.get("kind", "general")).strip() or "general"
    task_max_attempts = int(run_config.get("max_attempts", 5))

    upsert_task_record(
        {
            "task_file": task_relpath,
            "task_id": task_id,
            "title": task_title,
            "priority": task_priority,
            "project": project_path,
            "kind": task_kind,
            "status": "todo",
            "owner": "",
            "attempts": 0,
            "max_attempts": task_max_attempts,
            "blocked_by": "",
            "needs_human_reason": "",
            "last_run_id": "",
            "body_text": task_markdown,
        }
    )
    task_relpath = sync_task_record_to_file(task_relpath)
    task_file = ROOT / task_relpath

    print(f"Prepared task: {task_file.relative_to(ROOT)}")
    print(f"Project dir: {project_dir.relative_to(ROOT)}")
    print(f"Stack: {stack_id}")

    if start_mode == "auto":
        from commands.auto import main as auto_main

        auto_main()
        return

    if start_mode == "run":
        from commands.run import main as run_main

        run_main()
        return

    if start_mode != "prepare":
        raise ValueError(f"Unsupported start_mode: {start_mode}")


if __name__ == "__main__":
    main()
