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
- Create between 1 and 5 subtasks.
- Subtasks must be ordered for execution.
- Keep them safe, concrete, and testable.
- Do not invent backend or infra work if the task is purely frontend.
- Do not include explanations outside the JSON object.
