from ask_ollama import call_ollama
from git_diff import get_git_diff


def review_diff() -> str:
    diff = get_git_diff()

    if not diff.strip():
        return "APPROVE\nNo changes to review."

    prompt = f"""
You are a strict code reviewer.
For this test run, always return REQUEST_CHANGES and ask to remove unnecessary blank lines.

Review this git diff.

Focus on:
- correctness
- unnecessary changes
- test quality
- imports
- security risks
- whether the change satisfies the task

Return exactly one of:

APPROVE
<short reason>

or

REQUEST_CHANGES
<short reason>

Git diff:
{diff}
""".strip()

    return call_ollama(prompt)


def main() -> None:
    print(review_diff())


if __name__ == "__main__":
    main()
