# FlowMusic Toolkit Agent Guide

## Mission

Use this repository to back up a user's own FlowMusic (formerly Producer.ai, formerly Riffusion) music data safely and quickly.

Priority workflow:
1. Authenticate.
2. Run a small test.
3. Run full backup.
4. Export CSV.
5. Report results.

## Canonical Interface

Always prefer `node cli.js` commands.

Core commands:

```bash
node cli.js --help
node cli.js login
node cli.js download --all
node cli.js playlist "https://www.flowmusic.app/playlist/<uuid>"
node cli.js project "https://www.flowmusic.app/project/<uuid>"
node cli.js playlist-batch playlists.json
node cli.js status
node cli.js export
```

## Safe Operation Rules

- Use `download -n 1` or `-n 3` for first verification unless user explicitly asks to skip tests.
- Do not use `--reset` unless user asks for checkpoint reset.
- Report exact command run, output path, and summary counts.
- Keep operations local; do not send user content externally.
- Treat this as personal backup tooling, not content acquisition from other accounts.

## Repository Map

- `cli.js`: primary CLI entrypoint.
- `src/scrapers/fullLibraryScraper.js`: full-library, playlist, and project orchestration.
- `src/downloaders/completeSongDownloader.js`: per-song asset capture.
- `src/exporters/csvExporter.js`: CSV generation from metadata files.
- `config/scraper.config.js`: selectors, delays, checkpoint behavior, metadata defaults.
- `README.md`: user-facing documentation.
- `QUICKSTART.md`: shortest operational path.
- `RELEASE-CHECKLIST.md`: publish-readiness checklist.

## Skills Included

Portable skills live in `skills/` and follow shared `SKILL.md` format.

- `skills/producer-backup-operator`: end-to-end operating runbook.
- `skills/producer-backup-troubleshooter`: failure diagnosis and recovery.

## Copying Skills Across Agent Platforms

This repository now includes pre-generated platform folders:

- `.claude/skills/*`
- `.gemini/skills/*`
- `.opencode/skills/*`
- `.codex/skills/*`
- `.agents/skills/*`

Custom command packs are also included:

- `.claude/commands/*`
- `.gemini/commands/*`
- `.opencode/commands/*`
- `.codex/prompts/*` (Codex runs these via `/prompts:<name>`)
- `PLATFORM-COMMANDS.md` includes invocation details by platform.

Codex prompt discovery note:
- Prompt files load from `$CODEX_HOME/prompts`.
- To use this repo-local Codex pack directly, launch with:
  `CODEX_HOME=$PWD/.codex codex`

Optional user-level skill sync remains available:
- `./scripts/sync-skills.sh --dry-run`
- `./scripts/sync-skills.sh`

Optional user-level command sync remains available:
- `./scripts/sync-commands.sh --dry-run`
- `./scripts/sync-commands.sh`

Combined wrapper (skills + commands):
- `bash ./scripts/sync-all-agent-assets.sh --dry-run`
- `bash ./scripts/sync-all-agent-assets.sh`

## Troubleshooting Fast Path

1. Validate input and command flags.
2. Re-auth with `npm run login`.
3. Re-test with `node cli.js download -n 1`.
4. Resume full run.
5. Export and report current recoverable state.
