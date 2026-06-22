from adapters.git import get_git_review_text
from adapters.ollama import call_model
from core.actions import READ_CHANGES, REVIEW_DIFF
from core.capabilities import REVIEW_CHANGES
from prompts import render_prompt
from review_context import build_visual_review_context
from core.workflow import Step, run_step


def review_changes(diff: str) -> str:
    if not diff.strip():
        return "APPROVE\nNo changes to review."

    prompt = render_prompt(
        "review_user",
        diff=diff,
        visual_context=build_visual_review_context(),
    )
    return call_model(prompt)


def main() -> None:
    diff = run_step(
        Step(
            name="reviewer_read_diff_once",
            action=READ_CHANGES,
            role="reviewer",
            capability=REVIEW_CHANGES,
            func=get_git_review_text,
        )
    )
    print(
        run_step(
            Step(
                name="reviewer_decide_once",
                action=REVIEW_DIFF,
                role="reviewer",
                capability=REVIEW_CHANGES,
                func=review_changes,
                args=(diff,),
            )
        )
    )


if __name__ == "__main__":
    main()
