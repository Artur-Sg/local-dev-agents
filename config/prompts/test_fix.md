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

{required_file_format}
