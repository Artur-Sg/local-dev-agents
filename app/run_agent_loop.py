from pathlib import Path

from apply_files import apply_files
from env import get_agent_max_attempts
from git_diff import get_git_diff
from model_client import call_model
from prompts import render_prompt
from run_tests import run_tests
from git_status import has_uncommitted_changes
from review_diff import review_diff
from workflow import Step, clear_trace, run_step

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"
MAX_ATTEMPTS = get_agent_max_attempts()


def main() -> None:
    clear_trace()
    dirty = run_step(
        Step(
            name="check_worktree_clean",
            action="read_status",
            role="manager",
            func=has_uncommitted_changes,
        )
    )

    if dirty:
        print("=== REFUSING TO RUN ===")
        print("Sandbox has uncommitted changes.")
        print("Run one of:")
        print("  ./agent.sh approve")
        print("  ./agent.sh reject")
        raise SystemExit(1)

    original_task = TASK_PATH.read_text(encoding="utf-8")
    prompt = original_task

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"=== Attempt {attempt}/{MAX_ATTEMPTS}: Asking Model ===")
        role = "developer" if attempt == 1 else "fixer"
        answer = run_step(
            Step(
                name=f"attempt_{attempt}_generate",
                action="call_model",
                role=role,
                func=call_model,
                args=(prompt,),
            )
        )

        print("=== Applying files ===")
        try:
            written = run_step(
                Step(
                    name=f"attempt_{attempt}_apply_files",
                    action="write_files",
                    role=role,
                    func=apply_files,
                    args=(answer,),
                )
            )
        except Exception as exc:
            print(f"=== RESULT: BAD FORMAT ===")
            print(str(exc))
            prompt = render_prompt(
                "format_fix_prompt",
                original_task=original_task,
                bad_answer=answer,
                error=str(exc),
                required_file_format=render_prompt("required_file_format"),
            )
            continue

        for path in written:
            print(f"- {path.relative_to(ROOT)}")

        print("=== Running tests ===")
        code, output = run_step(
            Step(
                name=f"attempt_{attempt}_run_tests",
                action="run_tests",
                role="tester",
                func=run_tests,
            )
        )
        print(output)

        if code == 0:
            print("=== RESULT: PASS ===")
            diff = run_step(
                Step(
                    name=f"attempt_{attempt}_read_diff",
                    action="read_diff",
                    role="manager",
                    func=get_git_diff,
                )
            )
            print("=== Git diff ===")
            print(diff if diff.strip() else "No changes")

            print("=== Reviewer ===")
            review = review_diff()
            print(review)

            if review.strip().upper().startswith("APPROVE"):
                raise SystemExit(0)

            print("=== RESULT: REVIEW REQUESTED CHANGES ===")
            prompt = render_prompt(
                "review_fix_prompt",
                original_task=original_task,
                diff=diff,
                review=review,
                required_file_format=render_prompt("required_file_format"),
            )
            continue

        print("=== RESULT: FAIL ===")
        prompt = render_prompt(
            "test_fix_prompt",
            original_task=original_task,
            test_output=output,
            required_file_format=render_prompt("required_file_format"),
        )

    print("=== FINAL RESULT: FAIL ===")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
