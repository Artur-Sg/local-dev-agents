from apply_files import apply_files
from model_client import call_model
from run_tests import run_tests
from workflow import Step, clear_trace, run_step
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"


def main() -> None:
    clear_trace()
    prompt = TASK_PATH.read_text(encoding="utf-8")

    print("=== Asking Model ===")
    answer = run_step(
        Step(
            name="generate_solution",
            action="call_model",
            role="developer",
            func=call_model,
            args=(prompt,),
        )
    )

    print("=== Applying files ===")
    written = run_step(
        Step(
            name="apply_solution_files",
            action="write_files",
            role="developer",
            func=apply_files,
            args=(answer,),
        )
    )
    for path in written:
        print(f"- {path.relative_to(ROOT)}")

    print("=== Running tests ===")
    code, output = run_step(
        Step(
            name="run_tests",
            action="run_tests",
            role="tester",
            func=run_tests,
        )
    )
    print(output)

    if code == 0:
        print("=== RESULT: PASS ===")
    else:
        print("=== RESULT: FAIL ===")

    raise SystemExit(code)


if __name__ == "__main__":
    main()
