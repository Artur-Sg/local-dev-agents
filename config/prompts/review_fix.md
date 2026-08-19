The tests passed, but the code reviewer requested changes.

Original task:
{original_task}

Current project files:
{current_project_files}

Allowed output paths:
{allowed_paths}

Current git diff:
{diff}

Reviewer feedback:
{review}

Update the project to address the review feedback.

Requirements:
- Follow these incremental delivery rules:
{incremental_rules}
- Return all files that need to be created or changed.
- Do not add explanations.
- Do not use markdown code fences.
- Keep the tests passing.
- Write only to the allowed output paths listed above.
- Treat the current files as the baseline and preserve working UI structure unless the review explicitly requires a change.
- Prefer minimal diffs.
- Do not rewrite unrelated files.

{required_file_format}
