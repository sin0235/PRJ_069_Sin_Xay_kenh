---
description: Run a quick smoke-test backup
---
Use the `flowmusic-backup-operator` skill.
Goal: run a safe smoke-test backup.

Steps:
1. Ensure dependencies are installed (`npm install`) if needed.
2. If session is missing or expired, run `npm run login`.
3. Run `node cli.js download -n 3 --format mp3`.
4. Run `node cli.js status`.
5. Summarize commands run and key results.

Rules:
- Do not use `--reset`.
- Keep output in this repository.
