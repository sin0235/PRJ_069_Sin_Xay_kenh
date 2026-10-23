# Skills Pack

Canonical skill source in this repo:

- `skills/producer-backup-operator`
- `skills/producer-backup-troubleshooter`

Repo-local platform bundles are pre-generated:

- `.agents/skills/*`
- `.codex/skills/*`
- `.claude/skills/*`
- `.gemini/skills/*`
- `.opencode/skills/*`

These contain full skill folders (`SKILL.md`, `agents/`, `references/`) so cloned repos can be used directly by compatible agents.

## Commands Pack

Repo-local command packs are pre-generated:

- Codex prompts: `.codex/prompts/*.md` (invoked as `/prompts:<name>`)
- Claude commands: `.claude/commands/*.md`
- Gemini commands: `.gemini/commands/*.toml`
- OpenCode commands: `.opencode/commands/*.md`

Portable source template remains `SLASH-COMMANDS.md`.
Platform usage reference: `PLATFORM-COMMANDS.md`.

## Codex Prompt Note

Codex custom prompts load from `$CODEX_HOME/prompts`. To use the repo-local pack as-is:

```bash
CODEX_HOME=$PWD/.codex codex
```

## Optional User-Level Sync

One wrapper for both command and skill sync:

```bash
bash ./scripts/sync-all-agent-assets.sh --dry-run
bash ./scripts/sync-all-agent-assets.sh
```

If you prefer installing skills into your home directories:

```bash
./scripts/sync-skills.sh --dry-run
./scripts/sync-skills.sh
```

If you prefer installing command packs into user-level agent directories:

```bash
./scripts/sync-commands.sh --dry-run
./scripts/sync-commands.sh
```
