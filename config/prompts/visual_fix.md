The visual QA step reported layout or UI problems.

Original task:
{original_task}

Current project files:
{current_project_files}

Allowed output paths:
{allowed_paths}

Visual QA findings:
{visual_findings}

Update the project to fix the visual issues while keeping the task requirements intact.

Requirements:
- Follow these incremental delivery rules:
{incremental_rules}
- Return all files that need to be created or changed.
- Do not add explanations.
- Do not use markdown code fences.
- Keep existing realistic content unless the task requires changes.
- Write only to the allowed output paths listed above.
- Treat the current files as the baseline and refine them instead of resetting the page.
- Prefer minimal diffs.
- Do not rewrite unrelated files.

{required_file_format}
