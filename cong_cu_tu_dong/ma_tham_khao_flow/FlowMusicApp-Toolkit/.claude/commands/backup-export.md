---
description: Export metadata JSON to CSV
argument-hint: [output-path] [csv-path]
---
Use the `flowmusic-backup-operator` skill.
Goal: export metadata to CSV.

Input:
- Raw arguments: $ARGUMENTS

Argument handling:
- If empty, run `node cli.js export --output ./output`.
- If one value is provided, run `node cli.js export --output "$ARGUMENTS"`.
- If two values are provided, use first as output path and second as csv path.

Steps:
1. Parse arguments.
2. Resolve `OUTPUT_PATH` and optional `CSV_PATH`.
3. Run one of:
   - `node cli.js export --output ./output`
   - `node cli.js export --output "$OUTPUT_PATH"`
   - `node cli.js export --output "$OUTPUT_PATH" --csv-path "$CSV_PATH"`
4. Report CSV path and row/song count.
