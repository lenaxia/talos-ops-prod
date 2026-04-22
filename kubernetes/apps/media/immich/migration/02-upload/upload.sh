#!/usr/bin/env bash
# upload.sh — Bulk upload Synology Photos libraries into Immich
#
# Uses the official immich-cli Docker image so no local Node.js install needed.
# Deduplication is by SHA-1 hash — safe to re-run if interrupted.
#
# Prerequisites:
#   - users.env exists and is populated (copy from users.env.example)
#   - The NFS mounts are live inside the immich-server pod (Phase 1 complete)
#   - Docker is available on this machine
#   - The NFS paths are accessible from THIS machine (or adjust SOURCE_BASE_* below)
#
# The script uploads via the Immich HTTP API (not directly into the pod).
# Photos must be accessible on the machine running this script.
# If running from a machine that cannot NFS-mount the NAS, run this script
# from inside the cluster instead (kubectl run --rm -it ...).
#
# Usage:
#   ./upload.sh                    # upload all users
#   ./upload.sh --user mikek       # upload a single user only
#   ./upload.sh --dry-run          # show what would happen, no uploads

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/users.env"
LOG_DIR="${SCRIPT_DIR}/logs"
IMMICH_CLI_IMAGE="ghcr.io/immich-app/immich-cli:latest"

# NAS paths as mounted on THIS machine (adjust if different from pod mount points)
# If running from a machine with the NFS shares mounted:
SOURCE_BASE_LOCAL="/import/syno-local"   # NAS: /volume1/homes
SOURCE_BASE_LDAP="/import/syno-ldap"     # NAS: /volume1/homes/@LH-KAO.FAMILY/61

# CLI options applied to every upload
IMMICH_CLI_OPTS="--recursive --album --ignore '**/@eaDir/**' --no-progress"

# ---------------------------------------------------------------------------

usage() {
  echo "Usage: $0 [--user <username>] [--dry-run] [--help]"
  echo ""
  echo "  --user <name>   Upload only the specified user (e.g. --user mikek)"
  echo "  --dry-run       Pass --dry-run to immich-cli; no files are uploaded"
  echo "  --help          Show this help"
  exit 0
}

# Parse args
FILTER_USER=""
DRY_RUN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)     FILTER_USER="$2"; shift 2 ;;
    --dry-run)  DRY_RUN="--dry-run"; shift ;;
    --help)     usage ;;
    *)          echo "Unknown argument: $1"; usage ;;
  esac
done

# Load environment
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy users.env.example to users.env and fill in values."
  exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

# Validate required vars
: "${IMMICH_URL:?IMMICH_URL not set in users.env}"

mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------
# upload_paths <username> <api_key> <path1> [<path2> ...]
#
# Runs immich-cli for each source path under the given user's API key.
# ---------------------------------------------------------------------------
upload_paths() {
  local username="$1"
  local api_key="$2"
  shift 2
  local paths=("$@")

  if [[ -z "$api_key" ]]; then
    echo "[SKIP] $username — API key not set in users.env"
    return
  fi

  local log_file="${LOG_DIR}/upload-${username}-$(date +%Y%m%d-%H%M%S).log"
  echo "[START] $username → $log_file"

  for src_path in "${paths[@]}"; do
    if [[ ! -d "$src_path" ]]; then
      echo "[WARN]  $username — path does not exist on this machine: $src_path"
      echo "[WARN]  Skipping. If NFS is not mounted locally, run this script from inside the cluster."
      continue
    fi

    echo "[UPLOAD] $username ← $src_path"
    # shellcheck disable=SC2086
    docker run --rm \
      -v "${src_path}:/import:ro" \
      -e IMMICH_INSTANCE_URL="${IMMICH_URL}/api" \
      -e IMMICH_API_KEY="${api_key}" \
      "${IMMICH_CLI_IMAGE}" \
      upload ${IMMICH_CLI_OPTS} ${DRY_RUN} /import \
      2>&1 | tee -a "$log_file"
  done

  echo "[DONE]  $username"
}

# ---------------------------------------------------------------------------
# User definitions
# Format: upload_paths <username> <api_key> <path1> [<path2> ...]
#
# Users with two source paths (local + LDAP) upload both under one API key.
# immich-cli SHA-1 deduplicates so photos present in both paths are stored once.
# ---------------------------------------------------------------------------

run_user() {
  local name="$1"
  if [[ -n "$FILTER_USER" && "$FILTER_USER" != "$name" ]]; then
    return
  fi
  shift
  upload_paths "$name" "$@"
}

# mikek: Lenaxia (old local account) + mikek LDAP
run_user "mikek" "${MIKEK_API_KEY:-}" \
  "${SOURCE_BASE_LOCAL}/Lenaxia/Photos" \
  "${SOURCE_BASE_LDAP}/mikek-1000032/Photos"

# darcy: local account + LDAP account (merged into one Immich account)
run_user "darcy" "${DARCY_API_KEY:-}" \
  "${SOURCE_BASE_LOCAL}/darcy/Photos" \
  "${SOURCE_BASE_LDAP}/darcy-1000005/Photos"

# chuni: local account only
run_user "chuni" "${CHUNI_API_KEY:-}" \
  "${SOURCE_BASE_LOCAL}/chuni/Photos"

# steviek: local account + LDAP account
run_user "steviek" "${STEVIEK_API_KEY:-}" \
  "${SOURCE_BASE_LOCAL}/steviek/Photos" \
  "${SOURCE_BASE_LDAP}/steviek-1000006/Photos"

# adonia: local account only
run_user "adonia" "${ADONIA_API_KEY:-}" \
  "${SOURCE_BASE_LOCAL}/adonia/Photos"

# lola-poo: LDAP only
run_user "lola-poo" "${LOLA_POO_API_KEY:-}" \
  "${SOURCE_BASE_LDAP}/lola-poo-1000017/Photos"

# pandaria: LDAP only
run_user "pandaria" "${PANDARIA_API_KEY:-}" \
  "${SOURCE_BASE_LDAP}/pandaria-1000034/Photos"

# tjkao: LDAP only
run_user "tjkao" "${TJKAO_API_KEY:-}" \
  "${SOURCE_BASE_LDAP}/tjkao-1000018/Photos"

# ---------------------------------------------------------------------------

echo ""
echo "All uploads complete. Logs are in ${LOG_DIR}/"
echo ""
echo "Next steps:"
echo "  1. In Immich Admin UI → Jobs → Extract Metadata   → Run (all)"
echo "  2. In Immich Admin UI → Jobs → Generate Thumbnails → Run (all)"
echo "  3. In Immich Admin UI → Jobs → Detect Faces        → Run (all)"
echo "  4. Wait for ALL jobs to drain before running Phase 3 (face migration)."
