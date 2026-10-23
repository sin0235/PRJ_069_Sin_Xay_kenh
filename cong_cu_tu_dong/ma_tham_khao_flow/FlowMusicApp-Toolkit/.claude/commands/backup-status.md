---
description: Show backup progress status
argument-hint: [output-path]
---
Use the `flowmusic-backup-operator` skill.
Goal: show current backup status.

Input:
- Output path: $ARGUMENTS (default `./output` when empty)

Steps:
1. If output argument is empty, run:
   `node cli.js status --output ./output`
2. Otherwise run:
   `node cli.js status --output "$ARGUMENTS"`
3. Summarize key metrics and failed count.
