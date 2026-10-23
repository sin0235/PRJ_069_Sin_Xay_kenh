# Quick Start

Use this if you just need a backup quickly.

## 1. Install

```bash
npm install
npx playwright install chromium
```

Notes:
- No separate Browser MCP server is required — this toolkit drives the browser directly via Playwright.
- Playwright installs Chromium (~500 MB). Ensure you have sufficient disk space.

## 2. Login once

```bash
npm run login
```

Sign in to FlowMusic in the opened browser window, then close it. Your session is saved to `.browser-profile/` so you only need to do this once.

If Google OAuth shows "This browser or app may not be secure", try running the login command again — it usually succeeds on the second attempt.

## 3. Test with a few songs

```bash
node cli.js download -n 3
```

## 4. Back up everything

```bash
node cli.js download --all
```

This scrapes both your "My Songs" library and all session pages, then downloads everything found. A large library (~700 songs) takes roughly 2.5 hours at default speed.

Optional variants:

```bash
node cli.js download --all --format stems
node cli.js download --all --format mp3 --include-stems --speed fast
```

## 5. Export CSV

```bash
node cli.js export
```

## Useful commands

```bash
node cli.js --help
node cli.js status
node cli.js download --all --reset
node cli.js playlist "https://www.flowmusic.app/playlist/<uuid>"
node cli.js project "https://www.flowmusic.app/project/<uuid>"
node cli.js playlist-batch playlists.json
```

## If a run stops

Run the **same command again without `--reset`**. Checkpoints in `checkpoints/` record which songs have already been downloaded, so the run picks up where it left off and skips completed songs.

Only use `--reset` when you want to start completely fresh and re-download everything.
