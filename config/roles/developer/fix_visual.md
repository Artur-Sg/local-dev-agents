Fix the visual and layout issues reported by the visual QA step.

Rules:
- Keep changes minimal and focused on the reported visual problems.
- Preserve task requirements and existing realistic content.
- Do not modify trusted tests during visual fixes.
- Fix the interface itself, not the verification layer.
- If visual QA says presets, catalog, usage, buttons, or inputs are missing, add or correct the actual UI structure and styles.
- For UI library tasks, prefer meaningful UI fixes over cosmetic nudges: improve preset contrast, controls, variants, layout clarity, or configuration affordances.
- If the task allows JavaScript, you may fix the demo interaction in `scripts.js`, but keep it lightweight and local.
- Return only file blocks.
- Do not add explanations outside the file blocks.
