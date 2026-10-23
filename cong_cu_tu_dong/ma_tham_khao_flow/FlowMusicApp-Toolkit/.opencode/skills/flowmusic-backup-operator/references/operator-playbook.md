# Operator Playbook

## Emergency Backup Runbook

Run this when the user needs immediate preservation of account data.

```bash
npm install
npx playwright install chromium
npm run login
node cli.js download --all
node cli.js export
node cli.js status
```

## Guided Workflow (Safer Default)

Use this flow for new users.

1. Install dependencies.

```bash
npm install
npx playwright install chromium
```

2. Log in and persist session.

```bash
npm run login
```

3. Verify with a small download.

```bash
node cli.js download -n 3
```

4. Run full backup.

```bash
node cli.js download --all
```

Optional variants:

```bash
# Download stems ZIP as primary asset
node cli.js download --all --format stems

# Download MP3 + stems together
node cli.js download --all --format mp3 --include-stems

# Faster pacing
node cli.js download --all --speed fast
```

5. Export CSV index.

```bash
node cli.js export
```

6. Report status.

```bash
node cli.js status
```

## Playlist Workflows

### Single playlist

```bash
node cli.js playlist "https://www.flowmusic.app/playlist/<uuid>" --format mp3
node cli.js playlist "https://www.flowmusic.app/playlist/<uuid>" --format stems
node cli.js playlist "https://www.flowmusic.app/playlist/<uuid>" --format mp3 --include-stems --speed fast
```

## Project Workflow

### Single project

```bash
node cli.js project "https://www.flowmusic.app/project/<uuid>" --format mp3
node cli.js project "https://www.flowmusic.app/project/<uuid>" --format stems
node cli.js project "https://www.flowmusic.app/project/<uuid>" --format mp3 --include-stems --speed fast
```

### Batch playlists

1. Create local file from template.

```bash
cp playlists.example.json playlists.json
```

2. Replace UUID placeholders with real playlist URLs.
3. Run batch.

```bash
node cli.js playlist-batch playlists.json --format mp3
node cli.js playlist-batch playlists.json --format stems --speed fast
```

## Resume and Recovery

- Re-run the same command to resume from checkpoints.
- Use `--reset` only when user wants a clean restart.

```bash
node cli.js download --all --reset
```

## User Walkthrough Script

Use this wording pattern for non-technical users:

1. "First I will open login mode."
2. "After login, I will test with 3 songs."
3. "If test output looks correct, I will run full backup."
4. "Then I will export CSV and share completion stats."
