from fnmatch import fnmatch

from core.roles import read_config_prompt
from core.settings import get_project_dir
from core.verification_plan import get_active_visual_review


def build_visual_review_context() -> str:
    config = get_active_visual_review()
    file_patterns = config["files"]
    prompt_path = config["prompt"]
    inline_prompt = config.get("prompt_text", "").strip()

    parts: list[str] = []

    if inline_prompt:
        parts.append(inline_prompt)
    elif prompt_path:
        parts.append(read_config_prompt(prompt_path))

    project_dir = get_project_dir()
    seen_paths: set[str] = set()

    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue

        rel_path = path.relative_to(project_dir).as_posix()
        if rel_path in seen_paths:
            continue

        if not any(fnmatch(rel_path, pattern) for pattern in file_patterns):
            continue

        content = path.read_text(encoding="utf-8")
        parts.append(f"Current file: {rel_path}\n{content}")
        seen_paths.add(rel_path)

    return "\n\n".join(parts).strip()
