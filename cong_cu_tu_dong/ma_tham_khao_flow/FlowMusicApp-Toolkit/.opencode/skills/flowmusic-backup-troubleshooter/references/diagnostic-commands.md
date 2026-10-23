# Diagnostic Commands

Use these in order from least disruptive to most involved.

## 1. Command surface check

```bash
node cli.js --help
node cli.js download --help
```

## 2. Input validation checks

```bash
node cli.js download --format flac
node cli.js playlist-batch playlists.example.json
```

Expected:
- first command should fail with supported format list.
- second should run validation and proceed if JSON entries are valid.

## 3. Session/auth recheck

```bash
npm run login
```

Then run small test:

```bash
node cli.js download -n 1
```

## 4. Output and checkpoint checks

```bash
node cli.js status --output ./output
find output -type f -name '*.json' | wc -l
```

## 5. Playlist-specific checks

```bash
node cli.js playlist "https://www.flowmusic.app/playlist/<uuid>" --headless
```

If this fails, retry without `--headless` to inspect UI interactions.

## 6. Export checks

```bash
node cli.js export --output ./output
```
