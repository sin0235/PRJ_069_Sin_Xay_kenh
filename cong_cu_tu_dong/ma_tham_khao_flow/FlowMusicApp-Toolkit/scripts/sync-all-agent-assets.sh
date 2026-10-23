#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SKILLS_SCRIPT="${SCRIPT_DIR}/sync-skills.sh"
SYNC_COMMANDS_SCRIPT="${SCRIPT_DIR}/sync-commands.sh"

DRY_RUN=0
CREATE_MISSING=1
ONLY_PLATFORMS=""
SKILLS_ONLY=0
COMMANDS_ONLY=0

usage() {
  cat <<'USAGE'
Usage: ./scripts/sync-all-agent-assets.sh [options]

Sync both skills and command packs to local agent directories.

Options:
  --dry-run           Print actions without writing changes
  --no-create         Do not create missing target directories
  --only <csv>        Comma-separated platforms: codex,claude,gemini,opencode
  --skills-only       Sync only skills
  --commands-only     Sync only command packs
  -h, --help          Show this help message

Examples:
  ./scripts/sync-all-agent-assets.sh
  ./scripts/sync-all-agent-assets.sh --dry-run
  ./scripts/sync-all-agent-assets.sh --only codex,gemini
  ./scripts/sync-all-agent-assets.sh --commands-only --only claude
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-create)
      CREATE_MISSING=0
      shift
      ;;
    --only)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --only" >&2
        usage
        exit 1
      fi
      ONLY_PLATFORMS="$2"
      shift 2
      ;;
    --skills-only)
      SKILLS_ONLY=1
      shift
      ;;
    --commands-only)
      COMMANDS_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if (( SKILLS_ONLY && COMMANDS_ONLY )); then
  echo "Choose only one: --skills-only or --commands-only" >&2
  exit 1
fi

if [[ ! -x "${SYNC_SKILLS_SCRIPT}" ]]; then
  echo "Missing executable script: ${SYNC_SKILLS_SCRIPT}" >&2
  exit 1
fi

if [[ ! -x "${SYNC_COMMANDS_SCRIPT}" ]]; then
  echo "Missing executable script: ${SYNC_COMMANDS_SCRIPT}" >&2
  exit 1
fi

build_args() {
  local -a args=()
  if (( DRY_RUN )); then
    args+=(--dry-run)
  fi
  if (( ! CREATE_MISSING )); then
    args+=(--no-create)
  fi
  if [[ -n "${ONLY_PLATFORMS}" ]]; then
    args+=(--only "${ONLY_PLATFORMS}")
  fi
  if [[ ${#args[@]} -gt 0 ]]; then
    printf '%s\n' "${args[@]}"
  fi
}

mapfile -t FORWARD_ARGS < <(build_args)

echo "Syncing agent assets..."

if (( ! COMMANDS_ONLY )); then
  echo
  echo "==> Skills"
  "${SYNC_SKILLS_SCRIPT}" "${FORWARD_ARGS[@]}"
fi

if (( ! SKILLS_ONLY )); then
  echo
  echo "==> Commands"
  "${SYNC_COMMANDS_SCRIPT}" "${FORWARD_ARGS[@]}"
fi

echo
echo "All requested sync operations completed."
