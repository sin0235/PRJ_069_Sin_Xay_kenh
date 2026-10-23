---
description: Back up one playlist URL
---
Use the `flowmusic-backup-operator` skill.
Goal: back up a single playlist.

Input:
- Playlist URL: $ARGUMENTS

Steps:
1. If URL is missing, ask for it and stop.
2. Validate URL matches `https://www.flowmusic.app/playlist/<uuid>`.
3. Run `node cli.js playlist "$ARGUMENTS" --format mp3`.
4. Run `node cli.js status`.

Rules:
- If URL is invalid, stop and ask for a corrected URL.
- Summarize playlist result counts.
