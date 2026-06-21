from git_diff import get_git_diff
from model_client import call_model
from prompts import render_prompt
from workflow import Step, run_step


def review_diff() -> str:
    diff = run_step(
        Step(
            name="review_read_diff",
            action="read_diff",
            role="reviewer",
            func=get_git_diff,
        )
    )

    if not diff.strip():
        return "APPROVE\nNo changes to review."

    prompt = render_prompt("review_user_prompt", diff=diff)

    return run_step(
        Step(
            name="review_decide",
            action="review_diff",
            role="reviewer",
            func=call_model,
            args=(prompt,),
        )
    )


def main() -> None:
    print(review_diff())


if __name__ == "__main__":
    main()
