import re
import sys
from pathlib import Path

from roles import require_action
from settings import ROOT, get_sandbox_dir
from workflow import run_as

TARGET_DIR = get_sandbox_dir()

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

def apply_files(text: str) -> list[Path]:
    require_action("write_files")

    written = []

    for match in FILE_RE.finditer(text):
        rel_path = match.group("path").strip()
        content = clean_content(match.group("content"))

        if not is_safe_relative_path(rel_path):
            raise ValueError(f"Unsafe path: {rel_path}")

        out_path = TARGET_DIR / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        written.append(out_path)

    if not written:
        raise ValueError("No file blocks found in model output")

    return written


def main() -> None:
    text = sys.stdin.read()
    written = run_as("developer", apply_files, text)

    print("Written files:")
    for path in written:
        print(f"- {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
