# Platform Commands

This repo includes prebuilt command packs for each CLI agent platform.

## Command Set

All platforms include these command names:

- `backup-quick`
- `backup-full`
- `backup-playlist`
- `backup-project`
- `backup-batch`
- `backup-resume`
- `backup-status`
- `backup-export`
- `backup-verify`
- `backup-fix`
- `skills-sync`

## Folder Layout

- Codex prompts: `.codex/prompts/*.md`
- Claude commands: `.claude/commands/*.md`
- Gemini commands: `.gemini/commands/*.toml`
- OpenCode commands: `.opencode/commands/*.md`

## Invocation by Platform

### Codex

- Command form: `/prompts:<name>`
- Example: `/prompts:backup-full`
- Prompt source directory: `$CODEX_HOME/prompts`
- Use repo-local pack directly:

```bash
CODEX_HOME=$PWD/.codex codex
```

### Claude Code

- Command form: `/<name>`
- Example: `/backup-full`
- Project command directory: `.claude/commands/`

### Gemini CLI

- Command form: `/<name>`
- Example: `/backup-full`
- Project command directory: `.gemini/commands/`
- If commands were added while running, refresh with:

```bash
/commands reload
```

### OpenCode

- Command form: `/<name>`
- Example: `/backup-full`
- Project command directory: `.opencode/commands/`

## Sync to User-Level Install

If you want these commands available globally outside this repo:

```bash
./scripts/sync-commands.sh --dry-run
./scripts/sync-commands.sh
```

If you want commands and skills together, use:

```bash
bash ./scripts/sync-all-agent-assets.sh --dry-run
bash ./scripts/sync-all-agent-assets.sh
```

Default targets:

- Codex: `~/.codex/prompts`
- Claude: `~/.claude/commands`
- Gemini: `~/.gemini/commands`
- OpenCode: `~/.config/opencode/commands`
