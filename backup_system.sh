#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/runtime/backups"
LOG_DIR="${PROJECT_ROOT}/runtime/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="LMCP-AutoQuote-Backup-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"
LATEST_LINK="${BACKUP_DIR}/LMCP-AutoQuote-Backup_latest.tar.gz"
RETENTION_COUNT="${RETENTION_COUNT:-10}"

mkdir -p "${BACKUP_DIR}" "${LOG_DIR}"

LOG_FILE="${LOG_DIR}/backup_system.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

cleanup_old_backups() {
  log "Applying backup retention policy: keep latest ${RETENTION_COUNT} backup(s)."

  local backup_list=""
  backup_list="$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'LMCP-AutoQuote-Backup-*.tar.gz' | sort -r || true)"

  if [[ -z "${backup_list}" ]]; then
    log "No backups found for retention cleanup."
    return
  fi

  local count=0
  while IFS= read -r old_backup; do
    [[ -z "${old_backup}" ]] && continue
    count=$((count + 1))
    if [[ "${count}" -le "${RETENTION_COUNT}" ]]; then
      continue
    fi
    log "Removing old backup: ${old_backup}"
    rm -f "${old_backup}"
  done <<< "${backup_list}"
}

verify_archive() {
  if tar -tzf "${ARCHIVE_PATH}" >/dev/null 2>&1; then
    log "Backup archive verification passed: ${ARCHIVE_PATH}"
  else
    log "Backup archive verification failed: ${ARCHIVE_PATH}"
    return 1
  fi
}

main() {
  log "Starting LMCP backup from: ${PROJECT_ROOT}"
  log "Creating archive: ${ARCHIVE_PATH}"

  # Use RELATIVE excludes because tar runs with -C "${PROJECT_ROOT}" .
  tar -czf "${ARCHIVE_PATH}" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='dist' \
    --exclude='build' \
    --exclude='runtime/backups' \
    --exclude='runtime/logs' \
    -C "${PROJECT_ROOT}" .

  verify_archive

  ln -sfn "${ARCHIVE_NAME}" "${LATEST_LINK}"
  log "Updated latest backup symlink: ${LATEST_LINK}"

  cleanup_old_backups

  log "Backup completed successfully."
  log "Archive path: ${ARCHIVE_PATH}"
}

main "$@"


