# Verification

## Completion Checks

Run these after backup.

```bash
node cli.js status
node cli.js export
```

## Output Spot Checks

Count metadata files:

```bash
find output -type f -name '*.json' | wc -l
```

Count audio and stems files:

```bash
find output -type f \( -name '*.mp3' -o -name '*.wav' -o -name '*.m4a' -o -name '*-stems.zip' \) | wc -l
```

Check for missing pairs quickly by sampling:

```bash
find output -type f -name '*.json' | head -n 10
```

## Expected Layout

Library mode:
- `output/<Song>.mp3`
- `output/<Song>-stems.zip` (when `--format stems` or `--include-stems`)
- `output/<Song>.jpg|png`
- `output/<Song>.json`

Playlist mode:
- `output/<Playlist Name>/<Song>.mp3`
- `output/<Playlist Name>/<Song>-stems.zip` (when `--format stems` or `--include-stems`)
- `output/<Playlist Name>/<Song>.jpg|png`
- `output/<Playlist Name>/<Song>.json`

Project mode:
- `output/<Project Name>/<Song>.mp3`
- `output/<Project Name>/<Song>-stems.zip` (when `--format stems` or `--include-stems`)
- `output/<Project Name>/<Song>.jpg|png`
- `output/<Project Name>/<Song>.json`

## Handoff Summary Template

Use this summary format:

1. Command run.
2. Total successful/skipped/failed.
3. Output path.
4. CSV path.
5. Any unresolved failures.
