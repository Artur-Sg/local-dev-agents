import json
import urllib.request
from pathlib import Path

from env import get_agent_http_timeout, get_model_api_url
from roles import get_role_config
from runtime import get_current_role
from workflow import run_as

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"
MODEL_API_URL = get_model_api_url()
HTTP_TIMEOUT = get_agent_http_timeout()


def call_model(prompt: str) -> str:
    role = get_current_role()
    role_config = get_role_config(role)
    model = role_config["model"]

    if not model:
        raise ValueError(f"Role {role} does not define a model for model calls")

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": role_config["system_prompt"],
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MODEL_API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["message"]["content"]


def main() -> None:
    prompt = TASK_PATH.read_text(encoding="utf-8")
    answer = run_as("developer", call_model, prompt)
    print(answer)


if __name__ == "__main__":
    main()
