# Recovery Playbook

## Preserve Progress First

- Do not run `--reset` by default.
- Re-run prior command to resume checkpoint-based progress.

## Minimal-Risk Recovery Flow

1. Reproduce with smallest test.

```bash
node cli.js download -n 1
```

2. If test passes, resume intended run.

```bash
node cli.js download --all
```

3. If test fails only for one mode, switch mode.

Examples:
- library run fails, playlist run works: use playlist backups first.
- headless run fails, visible run works: continue non-headless.

4. Export and summarize partial results.

```bash
node cli.js export
node cli.js status
```

## Last-Resort Actions

Use only with user confirmation:

- `node cli.js download --all --reset`
- checkpoint cleanup under `checkpoints/`

## Communication Template

Use this incident summary structure:

1. Failure observed (command + short error).
2. Likely cause.
3. Fix attempted.
4. Verification command.
5. Current state and next command.
