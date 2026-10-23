# Release Checklist

Use this before publishing the repository.

## 1. Clean and verify local state

- Remove personal output artifacts if present: `output/*` (keep `output/.gitkeep`), `logs/`, `checkpoints/`
- Confirm `.env` is not committed
- Confirm `.browser-profile/` is not committed
- Confirm local agent state is not committed (`.claude/settings.local.json`, local `.codex`/`.gemini` runtime files, etc.)
- Run:

```bash
npm test
node cli.js --help
node cli.js project --help
bash ./scripts/sync-all-agent-assets.sh --dry-run --only codex,claude,gemini,opencode
```

## 2. Validate docs

- `README.md` commands run as written
- `QUICKSTART.md` reflects fastest path to backup
- `PLATFORM-COMMANDS.md` matches actual command filenames and invocation syntax
- License file exists (`LICENSE`)

## 3. Manual smoke run

- Login works: `npm run login`
- Test download works: `node cli.js download -n 1`
- Test project download works: `node cli.js project "https://www.flowmusic.app/project/<uuid>" --format mp3`
- CSV export works: `node cli.js export`
- Status works: `node cli.js status`

## 4. Privacy and security check

- No tokens, cookies, credentials, or profile dumps in tracked files
- No personal absolute paths in docs/scripts
- Metadata defaults are generic (not personal identity)

## 5. Optional but recommended

- Add a GitHub issue template for bug reports
- Add a CI workflow for `npm test`
- Tag release (for example `v1.0.0`) after first public commit
