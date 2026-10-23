#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ALL_PLATFORMS=("codex" "claude" "gemini" "opencode")

DRY_RUN=0
CREATE_MISSING=1
ONLY_PLATFORMS=""

usage() {
  cat <<'USAGE'
Usage: ./scripts/sync-commands.sh [options]

Sync FlowMusic Toolkit platform command packs to local agent command directories.

Options:
  --dry-run           Print actions without writing changes
  --no-create         Do not create missing target command directories
  --only <csv>        Comma-separated platforms: codex,claude,gemini,opencode
  -h, --help          Show this help message

Examples:
  ./scripts/sync-commands.sh
  ./scripts/sync-commands.sh --dry-run
  ./scripts/sync-commands.sh --only codex,gemini
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

platform_source_dir() {
  local platform="$1"
  case "$platform" in
    codex)   printf '%s/.codex/prompts' "${REPO_ROOT}" ;;
    claude)  printf '%s/.claude/commands' "${REPO_ROOT}" ;;
    gemini)  printf '%s/.gemini/commands' "${REPO_ROOT}" ;;
    opencode) printf '%s/.opencode/commands' "${REPO_ROOT}" ;;
    *)
      echo "Unknown platform: ${platform}" >&2
      return 1
      ;;
  esac
}

platform_target_dir() {
  local platform="$1"
  case "$platform" in
    codex)   printf '%s/.codex/prompts' "${HOME}" ;;
    claude)  printf '%s/.claude/commands' "${HOME}" ;;
    gemini)  printf '%s/.gemini/commands' "${HOME}" ;;
    opencode) printf '%s/.config/opencode/commands' "${HOME}" ;;
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

echo "Repository: ${REPO_ROOT}"
echo "Selected platforms: ${SELECTED_PLATFORMS[*]}"
if (( DRY_RUN )); then
  echo "Mode: dry-run"
fi

synced_count=0

for platform in "${SELECTED_PLATFORMS[@]}"; do
  source_root="$(platform_source_dir "${platform}")"
  target_root="$(platform_target_dir "${platform}")"

  if [[ ! -d "${source_root}" ]]; then
    echo "Skipping ${platform}: source directory not found (${source_root})"
    continue
  fi

  if [[ ! -d "${target_root}" ]]; then
    if (( CREATE_MISSING )); then
      run_cmd mkdir -p "${target_root}"
    else
      echo "Skipping ${platform}: target directory not found (${target_root})"
      continue
    fi
  fi

  copied_for_platform=0
  while IFS= read -r -d '' src; do
    filename="$(basename "${src}")"
    dest="${target_root}/${filename}"
    run_cmd cp -f "${src}" "${dest}"
    echo "Synced ${platform} command: ${filename} -> ${dest}"
    synced_count=$((synced_count + 1))
    copied_for_platform=$((copied_for_platform + 1))
  done < <(find "${source_root}" -maxdepth 1 -type f -print0 | sort -z)

  if [[ "${copied_for_platform}" -eq 0 ]]; then
    echo "No command files found for ${platform} at ${source_root}"
  fi
done

echo "Done. Synced ${synced_count} command files."
