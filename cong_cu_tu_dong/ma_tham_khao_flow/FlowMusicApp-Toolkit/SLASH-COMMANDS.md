# Slash Commands

Use these as portable slash-command definitions for CLI agents.

How to use:
- Create a custom slash command with the name shown.
- Paste the matching prompt body.
- Keep command execution in this repository root.

## /backup-quick

Purpose:
- Fast smoke test backup with minimal risk.

Prompt body:
```text
Use $producer-backup-operator.
Goal: run a quick backup smoke test.

Steps:
1. Ensure dependencies are available.
2. Run login flow if session is missing: npm run login
3. Run test download: node cli.js download -n 3
4. Run status: node cli.js status

Rules:
- Do not use --reset.
- Use mp3 unless I explicitly request another format.
- Summarize commands run and key results (successful/skipped/failed).
```

## /backup-full

Purpose:
- Full-library backup and export.

Prompt body:
```text
Use $producer-backup-operator.
Goal: perform a full backup of my FlowMusic library.

Steps:
1. Confirm login/session readiness.
2. Run: node cli.js download --all
3. Run: node cli.js export
4. Run: node cli.js status

Rules:
- Do not use --reset unless I ask.
- Report output path, total counts, and CSV file path.
```

## /backup-playlist <url>

Purpose:
- Backup a single playlist.

Prompt body:
```text
Use $producer-backup-operator.
Goal: back up one playlist URL.

Input:
- Playlist URL: {{url}}

Steps:
1. Validate URL matches https://www.flowmusic.app/playlist/<uuid>
2. Run: node cli.js playlist "{{url}}" --format mp3
3. Run: node cli.js status

Rules:
- If URL is invalid, stop and ask for corrected URL.
- Summarize results including playlist name and counts.
```

## /backup-project <url>

Purpose:
- Backup a single project.

Prompt body:
```text
Use $producer-backup-operator.
Goal: back up one project URL.

Input:
- Project URL: {{url}}

Steps:
1. Validate URL matches https://www.flowmusic.app/project/<uuid>
2. Run: node cli.js project "{{url}}" --format mp3
3. Run: node cli.js status

Rules:
- If URL is invalid, stop and ask for corrected URL.
- Summarize results including project name and counts.
```

## /backup-batch [json=playlists.json]

Purpose:
- Backup multiple playlists from JSON.

Prompt body:
```text
Use $producer-backup-operator.
Goal: run batch playlist backup.

Input:
- JSON file path (default playlists.json): {{json_path}}

Steps:
1. If missing, default to playlists.json.
2. Validate file exists and is JSON array format.
3. Run: node cli.js playlist-batch "{{json_path}}" --format mp3
4. Run: node cli.js status

Rules:
- Do not use --reset unless I request it.
- Report invalid entries skipped and per-playlist totals.
```

## /backup-resume

Purpose:
- Safely continue interrupted backup progress.

Prompt body:
```text
Use $producer-backup-operator.
Goal: resume interrupted backup with minimal rework.

Steps:
1. Inspect recent context/checkpoint to infer prior mode (library, playlist, project, or batch).
2. Re-run the same mode command without --reset.
3. Run: node cli.js status

Rules:
- If prior mode is unclear, ask one concise question before running.
- Prefer smallest safe confirmation run first when uncertain.
```

## /backup-status [output=./output]

Purpose:
- Show checkpoint and local output progress.

Prompt body:
```text
Use $producer-backup-operator.
Goal: show current backup status.

Input:
- Output path (default ./output): {{output_path}}

Steps:
1. If missing, default to ./output.
2. Run: node cli.js status --output "{{output_path}}"
3. Summarize key metrics and failed item count.
```

## /backup-export [output=./output] [csv-path=auto]

Purpose:
- Export metadata to CSV.

Prompt body:
```text
Use $producer-backup-operator.
Goal: export backup metadata to CSV.

Inputs:
- Output directory (default ./output): {{output_path}}
- CSV path (optional): {{csv_path}}

Steps:
1. If csv_path provided, run:
   node cli.js export --output "{{output_path}}" --csv-path "{{csv_path}}"
2. Otherwise run:
   node cli.js export --output "{{output_path}}"
3. Report CSV path and row/song count.
```

## /backup-verify [output=./output]

Purpose:
- Verify backup completeness quickly.

Prompt body:
```text
Use $producer-backup-operator.
Goal: verify backup artifact integrity.

Input:
- Output path (default ./output): {{output_path}}

Steps:
1. Run: node cli.js status --output "{{output_path}}"
2. Run JSON count:
   find "{{output_path}}" -type f -name '*.json' | wc -l
3. Run audio/stems count:
   find "{{output_path}}" -type f \( -name '*.mp3' -o -name '*.wav' -o -name '*.m4a' -o -name '*-stems.zip' \) | wc -l
4. Report counts and any obvious mismatch.
```

## /backup-fix

Purpose:
- Diagnose and recover from backup failures.

Prompt body:
```text
Use $producer-backup-troubleshooter.
Goal: diagnose and fix current backup failure.

Steps:
1. Capture failing command and concise error text.
2. Map issue to known error class.
3. Apply lowest-risk fix.
4. Re-test with smallest safe command.
5. Resume normal workflow once test passes.

Rules:
- Do not use --reset unless I approve.
- End with: cause, fix, verification command, and next step.
```

## /skills-sync

Purpose:
- Sync skills to local agent directories.

Prompt body:
```text
Goal: sync toolkit skills to local agent skill directories.

Steps:
1. Run dry run first:
   ./scripts/sync-skills.sh --dry-run
2. If dry run looks correct, run:
   ./scripts/sync-skills.sh
3. Report which targets were synced.

Optional:
- For selected targets only, use: ./scripts/sync-skills.sh --only codex,claude
```

## Notes

- These slash prompts assume repository root execution.
- Canonical CLI remains `node cli.js`.
- Skills required by these prompts live in `skills/`.
