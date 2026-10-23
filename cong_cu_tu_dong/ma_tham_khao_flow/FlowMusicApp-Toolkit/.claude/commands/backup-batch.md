---
description: Back up multiple playlists from JSON
argument-hint: [json-path]
---
Use the `flowmusic-backup-operator` skill.
Goal: run playlist batch backup.

Input:
- JSON file path: $ARGUMENTS (default `playlists.json` when empty)

Steps:
1. If argument is empty, use `playlists.json`.
2. Validate file exists and contains a JSON array.
3. Run one of:
   - `node cli.js playlist-batch playlists.json --format mp3`
   - `node cli.js playlist-batch "$ARGUMENTS" --format mp3`
4. Run `node cli.js status`.

Rules:
- Do not use `--reset` unless I ask.
- Report invalid entries skipped and per-playlist totals.
