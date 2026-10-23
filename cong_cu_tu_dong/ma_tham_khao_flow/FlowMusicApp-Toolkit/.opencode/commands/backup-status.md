---
description: Show backup progress status
---
Use the `flowmusic-backup-operator` skill.
Goal: show current backup status.

Input:
- Output path: $1 (default `./output` when empty)

Steps:
1. If `$1` is empty, run:
   `node cli.js status --output ./output`
2. Otherwise run:
   `node cli.js status --output "$1"`
3. Summarize key metrics and failed count.
