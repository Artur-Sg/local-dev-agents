from pathlib import Path

from ask_ollama import call_ollama
from apply_files import apply_files
from env import get_agent_max_attempts
from git_diff import get_git_diff
from run_tests import run_tests
from git_status import has_uncommitted_changes
from review_diff import review_diff

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"
MAX_ATTEMPTS = get_agent_max_attempts()


def required_format() -> str:
    return """
You MUST return only file blocks.
Do not add explanations.
Do not use markdown code fences.

Return one or more file blocks.
Each file block must use a safe relative path from the repo root.

Required output format:

### FILE: relative/path/from/repo/root
<full file content>

### FILE: another/relative/path.ext
<full file content>
""".strip()

def build_format_fix_prompt(original_task: str, bad_answer: str, error: str) -> str:
    return f"""
Your previous response could not be applied.

Original task:
{original_task}

Parser error:
{error}

Your previous response:
{bad_answer}

Return the solution again using the required format.

{required_format()}
""".strip()


def build_test_fix_prompt(original_task: str, test_output: str) -> str:
    return f"""
The previous solution failed tests.

Original task:
{original_task}

Test output:
{test_output}

Fix the project.

Requirements:
- Return all files again.
- Do not add explanations.
- Do not use markdown code fences.
- Do not use requests.
- Do not use async tests.
- Keep the project structure consistent.
- Modify only files needed to satisfy the task and fix the tests.
- If this is a FastAPI task, use fastapi.testclient.TestClient for tests.
- If this is a FastAPI task, import app correctly from the app module.

{required_format()}
""".strip()


def main() -> None:
    if has_uncommitted_changes():
        print("=== REFUSING TO RUN ===")
        print("Sandbox has uncommitted changes.")
        print("Run one of:")
        print("  ./agent.sh approve")
        print("  ./agent.sh reject")
        raise SystemExit(1)

    original_task = TASK_PATH.read_text(encoding="utf-8")
    prompt = original_task

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"=== Attempt {attempt}/{MAX_ATTEMPTS}: Asking Ollama ===")
        answer = call_ollama(prompt)

        print("=== Applying files ===")
        try:
            written = apply_files(answer)
        except Exception as exc:
            print(f"=== RESULT: BAD FORMAT ===")
            print(str(exc))
            prompt = build_format_fix_prompt(original_task, answer, str(exc))
            continue

        for path in written:
            print(f"- {path.relative_to(ROOT)}")

        print("=== Running tests ===")
        code, output = run_tests()
        print(output)

        if code == 0:
            print("=== RESULT: PASS ===")
            diff = get_git_diff()
            print("=== Git diff ===")
            print(diff if diff.strip() else "No changes")

            print("=== Reviewer ===")
            review = review_diff()
            print(review)

            if review.strip().upper().startswith("APPROVE"):
                raise SystemExit(0)

            print("=== RESULT: REVIEW REQUESTED CHANGES ===")
            prompt = f"""
        The tests passed, but the code reviewer requested changes.

        Original task:
        {original_task}

        Current git diff:
        {diff}

        Reviewer feedback:
        {review}

        Update the project to address the review feedback.

        Requirements:
        - Return all files that need to be created or changed.
        - Do not add explanations.
        - Do not use markdown code fences.
        - Keep the tests passing.
        - Prefer minimal diffs.
        - Do not rewrite unrelated files.

        {required_format()}
        """.strip()
            continue

        print("=== RESULT: FAIL ===")
        prompt = build_test_fix_prompt(original_task, output)

    print("=== FINAL RESULT: FAIL ===")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
