---
name: verify
description: Run the full check suite ({{CHECKS_NAMES}}) and report results. Use before every commit and whenever asked to check the project.
---

# Verify

{{^MONOREPO}}
Run from the repository root. If the scaffold does not exist yet (before F01 lands), say "verify: checks not set up yet (F01 creates them)" and stop.
{{/MONOREPO}}
{{#MONOREPO}}
Run from the app directory (`{{APP_DIR}}/`), never from the monorepo's root. If the scaffold does not exist yet (before F01 lands), say "verify: checks not set up yet (F01 creates them)" and stop.
{{/MONOREPO}}

Run these stages in order:

{{CHECKS_STEPS_MD}}

Keep output small:
- A passing stage needs one line in your report, not its log.
- When a stage fails, read only the failing part. For tests, re-run just the failing file: `{{TEST_ONE_CMD}}`.

If a stage fails, report the shortest decisive error lines, fix the cause, and re-run from that stage. Fix the code, never the check: do not skip, disable or loosen a test or a lint rule to get green. For a format failure, run `{{FORMAT_CMD}}`, then re-check.

End with this table:

{{CHECKS_TABLE_MD}}
