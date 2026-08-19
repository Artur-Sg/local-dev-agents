Choose the next subtask that should be worked on now.
Do not write code.

Return exactly one JSON object:
{
  "subtask_id": "id_of_next_subtask",
  "reason": "short reason"
}

Rules:
- Select only from subtasks that are not done.
- Prefer the earliest blocking or foundational subtask.
- For UI library work, prefer the subtask that produces the largest meaningful improvement in library capability or configurability, not the safest cosmetic tweak.
- Do not include explanations outside the JSON object.
