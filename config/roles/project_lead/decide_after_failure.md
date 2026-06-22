Decide what the team should do after a failed iteration.
Do not write code.

Return exactly one JSON object:
{
  "decision": "fix_tests" | "fix_visual" | "fix_review" | "needs_human",
  "reason": "short reason"
}

Rules:
- Use "fix_tests" when the failure is actionable by the developer.
- Use "fix_visual" when the layout or visual structure should be corrected by the developer.
- Use "fix_review" when reviewer feedback should be addressed directly.
- Use "needs_human" only when the task is ambiguous, contradictory, or unsafe to continue.
- Do not include explanations outside the JSON object.
