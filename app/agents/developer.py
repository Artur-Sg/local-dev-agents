from adapters.ollama import call_model


def generate_solution(prompt: str) -> str:
    return call_model(prompt)


def fix_tests(prompt: str) -> str:
    return call_model(prompt)


def fix_review(prompt: str) -> str:
    return call_model(prompt)
