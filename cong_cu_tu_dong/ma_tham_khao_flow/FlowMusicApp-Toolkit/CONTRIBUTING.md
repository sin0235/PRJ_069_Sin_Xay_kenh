# Contributing

## Setup

```bash
npm install
npx playwright install chromium
```

## Basic checks

```bash
npm test
node cli.js --help
```

## Pull request guidance

- Keep changes scoped and focused
- Update docs when behavior changes
- Do not commit local runtime artifacts (`output/`, `logs/`, `checkpoints/`, `.env`)
- Include reproduction steps for scraper/selector fixes

## Notes

FlowMusic UI can change frequently. Prefer robust selectors and include fallback logic when possible.
