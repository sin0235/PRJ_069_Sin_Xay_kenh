---
description: Export metadata JSON to CSV
---
Use the `flowmusic-backup-operator` skill.
Goal: export metadata to CSV.

Input:
- First arg (`$1`): output path (default `./output`)
- Second arg (`$2`): csv path (optional)

Steps:
1. If `$1` and `$2` are empty, run:
   `node cli.js export --output ./output`
2. If `$1` is set and `$2` is empty, run:
   `node cli.js export --output "$1"`
3. If `$1` and `$2` are set, run:
   `node cli.js export --output "$1" --csv-path "$2"`
4. Report CSV path and row/song count.
