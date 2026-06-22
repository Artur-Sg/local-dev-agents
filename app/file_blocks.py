import re
import sys
from fnmatch import fnmatch
from pathlib import Path

from core.actions import WRITE_FILES
from core.roles import require_action
from core.settings import ROOT, get_allowed_write_paths, get_project_dir
from core.workflow import Step, run_step

TARGET_DIR = get_project_dir()
ALLOWED_WRITE_PATHS = get_allowed_write_paths()

FILE_RE = re.compile(
    r"^### FILE:\s*(?P<path>[^\n]+)\n(?P<content>.*?)(?=^### FILE:|\Z)",
    re.MULTILINE | re.DOTALL,
)


def clean_content(content: str) -> str:
    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    return content.rstrip() + "\n"


def is_safe_relative_path(path: str) -> bool:
    p = Path(path)

    if p.is_absolute():
        return False

    if ".." in p.parts:
        return False

    blocked_parts = {
        ".git",
        ".ssh",
        ".env",
        ".ollama",
        "__pycache__",
        ".pytest_cache",
    }

    if any(part in blocked_parts for part in p.parts):
        return False

    blocked_suffixes = {
        ".pyc",
        ".pyo",
        ".pem",
        ".key",
        ".sqlite",
        ".db",
    }

    if p.suffix in blocked_suffixes:
        return False

    return True


def is_allowed_write_path(path: str, allowed_paths: list[str]) -> bool:
    if not allowed_paths:
        return True

    normalized_path = Path(path).as_posix()
    return any(fnmatch(normalized_path, pattern) for pattern in allowed_paths)


def write_file_blocks(text: str) -> list[Path]:
    require_action(WRITE_FILES)

    written = []

    for match in FILE_RE.finditer(text):
        rel_path = match.group("path").strip()
        content = clean_content(match.group("content"))

        if not is_safe_relative_path(rel_path):
            raise ValueError(f"Unsafe path: {rel_path}")

        if not is_allowed_write_path(rel_path, ALLOWED_WRITE_PATHS):
            raise ValueError(f"Path is not allowed for this project: {rel_path}")

        out_path = TARGET_DIR / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    if not written:
        raise ValueError("No file blocks found in model output")

    return written


def main() -> None:
    text = sys.stdin.read()
    written = run_step(
        Step(
            name="write_file_blocks_once",
            action=WRITE_FILES,
            role="developer",
            func=write_file_blocks,
            args=(text,),
        )
    )

    print("Written files:")
    for path in written:
        print(f"- {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
