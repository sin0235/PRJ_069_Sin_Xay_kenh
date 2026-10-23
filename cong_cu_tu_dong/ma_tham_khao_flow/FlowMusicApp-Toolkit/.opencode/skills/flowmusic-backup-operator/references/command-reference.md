# Command Reference

## Global

```bash
node cli.js --help
```

## login

```bash
node cli.js login [--profile ./.browser-profile]
```

Purpose:
- Open browser and save authenticated profile session.

## download

```bash
node cli.js download [options]
```

Options:
- `-a, --all`: Download all songs.
- `-n, --num <number>`: Download first N songs. Must be positive integer.
- `-f, --format <format>`: `mp3`, `wav`, `m4a`, or `stems`.
- `--include-stems`: Also download stems ZIP when available.
- `--speed <mode>`: `slow`, `normal`, `fast`, `turbo`.
- `--between-songs-ms <ms>`: Override between-song delay in milliseconds.
- `-o, --output <path>`: Output directory.
- `-p, --profile <path>`: Browser profile path.
- `--headless`: Run without visible browser UI.
- `--reset`: Clear checkpoint and restart.
- `--start-id <id>`: Start from song ID.
- `--end-id <id>`: End at song ID (inclusive).

Notes:
- `--start-id` and `--end-id` support bounded segment downloads.
- Start ID appearing after end ID is invalid.
- `--format stems` downloads only the stems ZIP as the primary asset.
- `--include-stems` can be combined with `mp3/wav/m4a` to save both audio and stems ZIP.

## playlist

```bash
node cli.js playlist <playlist-url> [options]
```

Required:
- URL format like `https://www.flowmusic.app/playlist/<uuid>`.

Options:
- `-f, --format <format>`: `mp3`, `wav`, `m4a`, or `stems`.
- `--include-stems`: Also download stems ZIP when available.
- `--speed <mode>`: `slow`, `normal`, `fast`, `turbo`.
- `--between-songs-ms <ms>`: Override between-song delay in milliseconds.
- `-o, --output <path>`: Output root directory.
- `-p, --profile <path>`: Browser profile path.
- `--headless`: Run without visible browser UI.
- `--reset`: Reset checkpoint for this playlist.

## project

```bash
node cli.js project <project-url> [options]
```

Required:
- URL format like `https://www.flowmusic.app/project/<uuid>`.

Options:
- `-f, --format <format>`: `mp3`, `wav`, `m4a`, or `stems`.
- `--include-stems`: Also download stems ZIP when available.
- `--speed <mode>`: `slow`, `normal`, `fast`, `turbo`.
- `--between-songs-ms <ms>`: Override between-song delay in milliseconds.
- `-o, --output <path>`: Output root directory.
- `-p, --profile <path>`: Browser profile path.
- `--headless`: Run without visible browser UI.
- `--reset`: Reset checkpoint for this project.

## playlist-batch

```bash
node cli.js playlist-batch <json-file> [options]
```

Input file:
- JSON array of playlist URL strings or `{ "url": "..." }` objects.
- Invalid entries are skipped and reported.

Options:
- `-f, --format <format>`: `mp3`, `wav`, `m4a`, or `stems`.
- `--include-stems`: Also download stems ZIP when available.
- `--speed <mode>`: `slow`, `normal`, `fast`, `turbo`.
- `--between-songs-ms <ms>`: Override between-song delay in milliseconds.
- `-o, --output <path>`: Output root directory.
- `-p, --profile <path>`: Browser profile path.
- `--headless`: Run without visible browser UI.
- `--reset`: Reset all playlist checkpoints.

## export

```bash
node cli.js export [--output ./output] [--csv-path ./output/library.csv]
```

Purpose:
- Export CSV from metadata JSON files.
- Supports flat output and playlist/project subdirectories.

## status

```bash
node cli.js status [--output ./output]
```

Purpose:
- Show local metadata file count for selected output path.
- Show checkpoint totals, failed count, and last update.
