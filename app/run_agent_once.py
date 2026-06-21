from ask_ollama import call_ollama
from apply_files import apply_files
from run_tests import run_tests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"


def main() -> None:
    prompt = TASK_PATH.read_text(encoding="utf-8")

    print("=== Asking Ollama ===")
    answer = call_ollama(prompt)

    print("=== Applying files ===")
    written = apply_files(answer)
    for path in written:
        print(f"- {path.relative_to(ROOT)}")

    print("=== Running tests ===")
    code, output = run_tests()
    print(output)

    if code == 0:
        print("=== RESULT: PASS ===")
    else:
        print("=== RESULT: FAIL ===")

    raise SystemExit(code)


if __name__ == "__main__":
    main()
