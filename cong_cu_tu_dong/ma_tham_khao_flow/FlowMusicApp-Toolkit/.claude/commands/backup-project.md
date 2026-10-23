---
description: Back up one project URL
argument-hint: <project-url>
---
Use the `flowmusic-backup-operator` skill.
Goal: back up a single project.

Input:
- Project URL: $ARGUMENTS

Steps:
1. If URL is missing, ask for it and stop.
2. Validate URL matches `https://www.flowmusic.app/project/<uuid>`.
3. Run `node cli.js project "$ARGUMENTS" --format mp3`.
4. Run `node cli.js status`.

Rules:
- If URL is invalid, stop and ask for a corrected URL.
- Summarize project result counts.
