---
description: Verify backup completeness quickly
argument-hint: [output-path]
---
Use the `flowmusic-backup-operator` skill.
Goal: verify backup artifact integrity.

Input:
- Output path: $ARGUMENTS (default `./output` when empty)

Steps:
1. Resolve `OUTPUT_PATH`:
   - `./output` when no argument is provided.
   - `$ARGUMENTS` when provided.
2. Run `node cli.js status --output "$OUTPUT_PATH"`.
3. Count metadata files:
   `find "$OUTPUT_PATH" -type f -name '*.json' | wc -l`
4. Count audio/stems files:
   `find "$OUTPUT_PATH" -type f \( -name '*.mp3' -o -name '*.wav' -o -name '*.m4a' -o -name '*-stems.zip' \) | wc -l`
5. Report counts and obvious mismatches.
