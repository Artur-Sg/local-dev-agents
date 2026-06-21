import json
import urllib.request
from pathlib import Path

from env import get_agent_http_timeout, get_ollama_model, get_ollama_url

ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks" / "task.md"
OLLAMA_URL = get_ollama_url()
OLLAMA_MODEL = get_ollama_model()
HTTP_TIMEOUT = get_agent_http_timeout()


def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful coding assistant. "
                    "Return only requested file blocks. "
                    "Do not add explanations. "
                    "Do not use markdown code fences."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["message"]["content"]


def main() -> None:
    prompt = TASK_PATH.read_text(encoding="utf-8")
    answer = call_ollama(prompt)
    print(answer)


if __name__ == "__main__":
    main()
