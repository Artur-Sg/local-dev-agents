Break the task into a short, practical delivery plan.
Do not write code.

Return exactly one JSON object:
{
  "summary": "short summary",
  "subtasks": [
    {
      "id": "stable_id",
      "title": "short title",
      "description": "what should be done",
      "acceptance_criteria": [
        "specific outcome"
      ]
    }
  ]
}

Rules:
- Create only as many subtasks as necessary. Prefer the smallest coherent plan.
- Subtasks must be ordered for execution.
- Keep them safe, concrete, and testable.
- Do not invent backend or infra work if the task is purely frontend.
- For frontend library tasks, the first subtask must establish the core structure and reusable primitives before polish work.
- For frontend library tasks, prefer subtasks that add meaningful capability: stronger component API, clearer variant system, richer configuration controls, or visibly more distinct presets.
- Avoid decomposing the work into tiny cosmetic edits like "adjust one button style" if the task asks for a library-like step forward.
- Do not start with isolated copywriting or catalog decoration if foundational sections, component classes, and configuration hooks are still missing.
- Do not include explanations outside the JSON object.
