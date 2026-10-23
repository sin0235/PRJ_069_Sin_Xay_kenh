---
description: Diagnose and recover from backup failures
---
Use the `flowmusic-backup-troubleshooter` skill.
Goal: diagnose and fix the current backup failure.

Steps:
1. Capture failing command and concise error text.
2. Map issue to known error class.
3. Apply the lowest-risk fix.
4. Re-test with the smallest safe command.
5. Resume normal workflow after test passes.

Rules:
- Do not use `--reset` unless I approve.
- End with: cause, fix, verification command, next step.
