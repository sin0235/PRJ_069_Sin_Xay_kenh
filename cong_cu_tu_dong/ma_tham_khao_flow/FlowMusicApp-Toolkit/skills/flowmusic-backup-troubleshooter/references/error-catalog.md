# Error Catalog

## Unsupported format

Symptom:
- `Unsupported format "...". Use one of: mp3, wav, m4a`

Fix:
- Use only `mp3`, `wav`, or `m4a`.

## Invalid --num

Symptom:
- `Invalid --num "...". It must be a positive integer.`

Fix:
- Use positive integer.
- Example: `node cli.js download -n 3`

## Invalid playlist URL

Symptom:
- `Invalid playlist URL. Expected: https://www.flowmusic.app/playlist/<UUID>`

Fix:
- Use canonical playlist URL with UUID.

## Invalid playlist-batch JSON format

Symptom:
- `Invalid JSON format. Expected an array.`

Fix:
- Convert file to JSON array.

## No valid playlist URLs found

Symptom:
- `No valid playlist URLs found in JSON file`

Fix:
- Ensure each element is either URL string or object with `url` field.
- Ensure URLs match `/playlist/<uuid>`.

## No songs found / empty scrape

Likely causes:
- Session not authenticated.
- FlowMusic layout changed.
- Wrong page loaded.

Fix order:
1. Re-login with `npm run login`.
2. Run `node cli.js download -n 1` to retest.
3. If still failing, inspect selectors in `config/scraper.config.js`.

## Download timeout waiting for event "download"

Likely causes:
- Menu/format click did not trigger download.
- Temporary site/network issue.
- Slow response.

Fix order:
1. Re-run with small batch.
2. Retry without `--headless` to observe UI.
3. If reproducible on many songs, inspect menu selectors and flow in downloader.

## Export found zero songs

Likely causes:
- Wrong `--output` path.
- No metadata JSON files generated.

Fix:
1. Run `node cli.js status --output <path>`.
2. Count JSON files in output path.
3. Re-run download to produce metadata.

## Status mismatch with output

Likely causes:
- Comparing checkpoint from one run against different output path.

Fix:
- Always report both output path used for status and checkpoint totals from `checkpoints/library-scrape.json`.
