The previous solution failed tests.

Original task:
{original_task}

Current project files:
{current_project_files}

Allowed output paths:
{allowed_paths}

Test output:
{test_output}

Fix the project.

Requirements:
- Follow these incremental delivery rules:
{incremental_rules}
- Return all files again.
- Do not add explanations.
- Do not use markdown code fences.
- Do not use requests.
- Do not use async tests.
- Keep the project structure consistent.
- Write only to the allowed output paths listed above.
- Treat the current files as the baseline and improve them instead of replacing the project with a different layout.
- Modify only files needed to satisfy the task and fix the tests.
- If this is a FastAPI task, use fastapi.testclient.TestClient for tests.
- If this is a FastAPI task, import app correctly from the app module.

{required_file_format}
