---
description: Export metadata JSON to CSV
argument-hint: [output-path] [csv-path]
---
Use the `flowmusic-backup-operator` skill.
Goal: export metadata to CSV.

Input:
- `$1`: output path (optional, default `./output`)
- `$2`: csv path (optional)

Steps:
1. If both args are empty, run:
   `node cli.js export --output ./output`
2. If only `$1` is set, run:
   `node cli.js export --output "$1"`
3. If `$1` and `$2` are set, run:
   `node cli.js export --output "$1" --csv-path "$2"`
4. Report CSV path and row/song count.
