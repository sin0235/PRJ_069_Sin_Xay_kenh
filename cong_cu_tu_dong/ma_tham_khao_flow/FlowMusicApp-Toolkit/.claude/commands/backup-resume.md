---
description: Resume interrupted backup safely
---
Use the `flowmusic-backup-operator` skill.
Goal: continue an interrupted backup with minimal rework.

Steps:
1. Inspect checkpoints/logs to infer prior mode (library, playlist, project, or batch).
2. Re-run the same mode command without `--reset`.
3. Run `node cli.js status`.

Rules:
- If prior mode is unclear, ask one concise question before running.
- Prefer a small confirmation run first when uncertain.
