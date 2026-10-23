#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILLS_ROOT="${REPO_ROOT}/skills"

ALL_PLATFORMS=("codex" "claude" "gemini" "opencode")
SKILL_FOLDERS=("flowmusic-backup-operator" "flowmusic-backup-troubleshooter")

DRY_RUN=0
CREATE_MISSING=1
ONLY_PLATFORMS=""

usage() {
  cat <<'USAGE'
Usage: ./scripts/sync-skills.sh [options]

Sync FlowMusic Toolkit skills to local agent skill directories.

Options:
  --dry-run           Print actions without writing changes
  --no-create         Do not create missing target skill directories
  --only <csv>        Comma-separated platforms: codex,claude,gemini,opencode
  -h, --help          Show this help message

Examples:
  ./scripts/sync-skills.sh
  ./scripts/sync-skills.sh --dry-run
  ./scripts/sync-skills.sh --only codex,claude
USAGE
}

contains() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    if [[ "$item" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

run_cmd() {
  if (( DRY_RUN )); then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

platform_target_dir() {
  local platform="$1"
  case "$platform" in
    codex)   printf '%s/.codex/skills' "${HOME}" ;;
    claude)  printf '%s/.claude/skills' "${HOME}" ;;
    gemini)  printf '%s/.gemini/skills' "${HOME}" ;;
    opencode) printf '%s/.config/opencode/skills' "${HOME}" ;;
    *)
      echo "Unknown platform: ${platform}" >&2
      return 1
      ;;
  esac
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

if [[ ! -d "${SKILLS_ROOT}" ]]; then
  echo "Skills directory not found: ${SKILLS_ROOT}" >&2
  exit 1
fi

SELECTED_PLATFORMS=()
if [[ -n "${ONLY_PLATFORMS}" ]]; then
  IFS=',' read -r -a requested <<< "${ONLY_PLATFORMS}"
  for platform in "${requested[@]}"; do
    trimmed="${platform//[[:space:]]/}"
    if [[ -z "${trimmed}" ]]; then
      continue
    fi
    if ! contains "${trimmed}" "${ALL_PLATFORMS[@]}"; then
      echo "Invalid platform in --only: ${trimmed}" >&2
      echo "Allowed: ${ALL_PLATFORMS[*]}" >&2
      exit 1
    fi
    SELECTED_PLATFORMS+=("${trimmed}")
  done
else
  SELECTED_PLATFORMS=("${ALL_PLATFORMS[@]}")
fi

if [[ ${#SELECTED_PLATFORMS[@]} -eq 0 ]]; then
  echo "No platforms selected" >&2
  exit 1
fi

for skill in "${SKILL_FOLDERS[@]}"; do
  if [[ ! -d "${SKILLS_ROOT}/${skill}" ]]; then
    echo "Missing source skill folder: ${SKILLS_ROOT}/${skill}" >&2
    exit 1
  fi
done

echo "Repository: ${REPO_ROOT}"
echo "Skills source: ${SKILLS_ROOT}"
echo "Selected platforms: ${SELECTED_PLATFORMS[*]}"
if (( DRY_RUN )); then
  echo "Mode: dry-run"
fi

synced_count=0

for platform in "${SELECTED_PLATFORMS[@]}"; do
  target_root="$(platform_target_dir "${platform}")"

  if [[ ! -d "${target_root}" ]]; then
    if (( CREATE_MISSING )); then
      run_cmd mkdir -p "${target_root}"
    else
      echo "Skipping ${platform}: target directory not found (${target_root})"
      continue
    fi
  fi

  for skill in "${SKILL_FOLDERS[@]}"; do
    src="${SKILLS_ROOT}/${skill}"
    dest="${target_root}/${skill}"

    run_cmd rm -rf "${dest}"
    run_cmd cp -R "${src}" "${dest}"

    echo "Synced ${skill} -> ${platform} (${dest})"
    synced_count=$((synced_count + 1))
  done
done

echo "Done. Synced ${synced_count} skill copies."
