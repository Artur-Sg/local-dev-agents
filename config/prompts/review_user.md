Review this git diff.

Your job is to decide whether this change is safe enough to accept.

Return REQUEST_CHANGES only for real blocking issues:
- code is likely broken
- tests are missing for the requested behavior
- task requirements are not satisfied
- imports are invalid
- security risk
- unrelated large rewrite
- generated files or secrets are added
- the diff changes files unrelated to the task

Do NOT return REQUEST_CHANGES for minor non-blocking issues:
- harmless naming differences
- small formatting changes
- extra useful tests
- removing unused imports
- minor style preferences
- small readable refactors

If the change is acceptable but has small comments, return APPROVE with notes.

Return exactly one of:

APPROVE
<short reason>

or

REQUEST_CHANGES
<short reason>

Git diff:
{diff}

Additional visual/web context:
{visual_context}
