Choose the next task that should enter delivery now.
Do not write code.

Return exactly one JSON object:
{
  "task_file": "tasks/inbox/file.md",
  "reason": "short reason"
}

Rules:
- Select only from the task files listed in the prompt.
- Prefer the most important, concrete, and executable task.
- Use metadata like task_id, priority, project, kind, title, attempts, and blocked_by when present.
- Avoid tasks that are vague, duplicated, or likely blocked by missing information.
- Do not include explanations outside the JSON object.
