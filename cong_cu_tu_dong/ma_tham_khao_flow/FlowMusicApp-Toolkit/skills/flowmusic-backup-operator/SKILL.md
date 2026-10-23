---
name: flowmusic-backup-operator
description: Operate the FlowMusic Toolkit CLI for end-to-end backup workflows. Use when a user asks to back up/download songs, run full-library export, run playlist or batch playlist downloads, resume interrupted downloads, check backup status, export CSV, or get a guided step-by-step walkthrough of toolkit usage.
---

# FlowMusic Backup Operator

Use this skill to run the toolkit safely and quickly, especially for time-sensitive backup windows.

## Core Workflow

1. Confirm environment readiness.
2. Run login flow if session is missing.
3. Run a small test download.
4. Run full or playlist-targeted backup.
5. Run status and export.
6. Report results with exact command and outcome.

## Command Selection

- Use `download --all` for full account backup.
- Use `download -n <N>` for quick smoke tests.
- Use `playlist <url>` for one playlist.
- Use `playlist-batch <json-file>` for many playlists.
- Use `status` to report checkpoint and local file counts.
- Use `export` after downloads complete.

## Execution Rules

- Use `node cli.js` as the canonical interface.
- Default to `mp3` unless user asks for another supported format.
- Validate risky arguments before long runs: `--num` must be positive integer, `--format` must be `mp3|wav|m4a`, and playlist URL must match `/playlist/<uuid>`.
- Run a short test first when user did not explicitly request full run immediately.
- Keep users informed of progress and next expected step.

## Reference Files

- Read `references/operator-playbook.md` for end-to-end runbooks.
- Read `references/command-reference.md` for complete command/options catalog.
- Read `references/verification.md` for output validation and handoff checks.
