from fnmatch import fnmatch

from core.settings import get_allowed_write_paths, get_project_dir


def _iter_context_paths() -> list[str]:
    project_dir = get_project_dir()
    allowed_paths = get_allowed_write_paths()
    found: list[str] = []

    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue

        rel_path = path.relative_to(project_dir).as_posix()
        if allowed_paths and not any(fnmatch(rel_path, pattern) for pattern in allowed_paths):
            continue

        found.append(rel_path)

    return found


def build_project_context() -> str:
    project_dir = get_project_dir()
    parts: list[str] = []

    for rel_path in _iter_context_paths():
        content = (project_dir / rel_path).read_text(encoding="utf-8")
        parts.append(
            "\n".join(
                [
                    f"<existing-file path=\"{rel_path}\">",
                    content.rstrip(),
                    "</existing-file>",
                ]
            )
        )

    if not parts:
        return "- no editable project files found yet"

    return "\n\n".join(parts)


def build_allowed_paths_text() -> str:
    allowed_paths = get_allowed_write_paths()

    if not allowed_paths:
        return "- any safe relative path inside the project"

    return "\n".join(f"- {path}" for path in allowed_paths)
