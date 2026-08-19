import json
import sys
import urllib.request

from core.roles import build_system_prompt, get_capability_config, get_role_config, require_action
from core.runtime import get_current_capability, get_current_role
from core.actions import CALL_MODEL
from core.capabilities import GENERATE_SOLUTION
from core.workflow import Step, run_step
from env import get_agent_http_timeout, get_model_api_url

MODEL_API_URL = get_model_api_url()
HTTP_TIMEOUT = get_agent_http_timeout()


def request_model(model: str, system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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


def call_model(prompt: str) -> str:
    require_action(CALL_MODEL)

    role = get_current_role()
    capability = get_current_capability()
    role_config = get_role_config(role)
    model = role_config["model"]

    if not model:
        raise ValueError(f"Role {role} does not define a model for model calls")

    if not capability:
        raise ValueError(f"Role {role} must run call_model within a capability context")

    get_capability_config(role, capability)

    return request_model(model, build_system_prompt(role, capability), prompt)


def main() -> None:
    prompt = sys.stdin.read().strip()
    if not prompt:
        raise SystemExit("Pass the user prompt via stdin.")
    answer = run_step(
        Step(
            name="call_model_once",
            action=CALL_MODEL,
            role="developer",
            capability=GENERATE_SOLUTION,
            func=call_model,
            args=(prompt,),
        )
    )
    print(answer)


if __name__ == "__main__":
    main()
