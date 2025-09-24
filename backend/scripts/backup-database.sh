#!/bin/bash

# Production Database Backup Script
# Daily automated backup with rotation and validation

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="${DATABASE_NAME:-oneshot_prod}"
DB_USER="${DATABASE_USER:-postgres}"
S3_BACKUP_BUCKET="${S3_BACKUP_BUCKET:-oneshot-prod-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="oneshot_db_${TIMESTAMP}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${BACKUP_DIR}/backup.log"
}

# Error handling
cleanup() {
    if [[ -f "${BACKUP_PATH}" ]]; then
        rm -f "${BACKUP_PATH}"
        log "ERROR: Cleanup - removed failed backup file"
    fi
}
trap cleanup ERR

# Create backup directory
mkdir -p "${BACKUP_DIR}"

log "Starting database backup for ${DB_NAME}"

# Validate database connection
if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
    log "ERROR: Cannot connect to database ${DB_HOST}:${DB_PORT}"
    exit 1
fi

# Create backup with compression
log "Creating backup: ${BACKUP_FILE}"
pg_dump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --verbose \
    --clean \
    --if-exists \
    --create \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_PATH}"

# Validate backup file
if [[ ! -f "${BACKUP_PATH}" ]] || [[ ! -s "${BACKUP_PATH}" ]]; then
    log "ERROR: Backup file is missing or empty"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
log "Backup created successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Test backup integrity
log "Validating backup integrity"
if ! pg_restore --list "${BACKUP_PATH}" >/dev/null 2>&1; then
    log "ERROR: Backup file is corrupted"
    exit 1
fi

log "Backup validation passed"

# Upload to S3 if configured
if [[ -n "${S3_BACKUP_BUCKET}" ]] && command -v aws >/dev/null 2>&1; then
    log "Uploading backup to S3: s3://${S3_BACKUP_BUCKET}/"
    
    aws s3 cp "${BACKUP_PATH}" "s3://${S3_BACKUP_BUCKET}/daily/" \
        --storage-class STANDARD_IA \
        --metadata "backup-date=${TIMESTAMP},database=${DB_NAME}"
    
    if [[ $? -eq 0 ]]; then
        log "S3 upload successful"
    else
        log "WARNING: S3 upload failed"
    fi
fi

# Cleanup old local backups
log "Cleaning up backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "oneshot_db_*.sql" -type f -mtime +${RETENTION_DAYS} -delete
OLD_LOGS=$(find "${BACKUP_DIR}" -name "backup.log.*" -type f -mtime +7 -delete 2>/dev/null | wc -l)

if [[ ${OLD_LOGS} -gt 0 ]]; then
    log "Removed ${OLD_LOGS} old log files"
fi

# Rotate log file weekly
LOG_SIZE=$(du "${BACKUP_DIR}/backup.log" 2>/dev/null | cut -f1 || echo "0")
if [[ ${LOG_SIZE} -gt 10240 ]]; then  # 10MB
    mv "${BACKUP_DIR}/backup.log" "${BACKUP_DIR}/backup.log.$(date +%Y%m%d)"
    log "Log file rotated"
fi

# Generate backup report
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "oneshot_db_*.sql" -type f | wc -l)
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)

log "Backup completed successfully"
log "Total backups: ${BACKUP_COUNT}, Total size: ${TOTAL_SIZE}"

# Send notification if webhook configured
if [[ -n "${BACKUP_WEBHOOK_URL:-}" ]]; then
    curl -X POST "${BACKUP_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{
            \"status\": \"success\",
            \"backup_file\": \"${BACKUP_FILE}\",
            \"backup_size\": \"${BACKUP_SIZE}\",
            \"timestamp\": \"${TIMESTAMP}\",
            \"database\": \"${DB_NAME}\"
        }" \
        --silent --fail || log "WARNING: Webhook notification failed"
fi

log "Database backup process completed"