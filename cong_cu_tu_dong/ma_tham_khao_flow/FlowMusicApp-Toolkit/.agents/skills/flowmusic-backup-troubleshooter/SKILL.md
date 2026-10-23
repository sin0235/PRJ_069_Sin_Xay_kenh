---
name: flowmusic-backup-troubleshooter
description: Diagnose and fix FlowMusic Toolkit failures. Use when backup commands fail, login/session is not recognized, playlists are rejected, downloads stall or timeout, no songs are found, CSV export is empty, or users need a structured recovery plan with minimal data loss.
---

# FlowMusic Backup Troubleshooter

Use this skill to triage failures quickly and restore backup progress with the least rework.

## Triage Workflow

1. Capture failing command, exact error text, and intended goal.
2. Classify failure type.
3. Apply targeted fix.
4. Re-run smallest safe verification command.
5. Resume full workflow after verification passes.

## Failure Classes

- Input validation failures.
- Authentication/profile failures.
- Site interaction failures (selectors/menu changes).
- Download timeouts.
- Empty/partial output issues.
- Export/status mismatches.

## Execution Rules

- Prefer incremental retest (`-n 1` or `-n 3`) before full rerun.
- Avoid `--reset` unless user explicitly wants to discard checkpoint progress.
- Preserve evidence: keep failing command lines, short error excerpts, output path, and checkpoint path.
- Escalate to selector/config inspection only after basic auth/input checks pass.

## Reference Files

- Read `references/error-catalog.md` for symptom-to-fix mapping.
- Read `references/diagnostic-commands.md` for safe debug command set.
- Read `references/recovery-playbook.md` for resume and fallback procedures.
