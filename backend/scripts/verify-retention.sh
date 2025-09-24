#!/bin/bash

# Production Data Retention Job Verification Script
# Verifies that retention cleanup jobs are running correctly

set -euo pipefail

# Configuration
LOG_FILE="/var/log/retention-verification.log"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="${DATABASE_NAME:-oneshot_prod}"
DB_USER="${DATABASE_USER:-postgres}"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Database query function
query_db() {
    local query="$1"
    PGPASSWORD="${DATABASE_PASSWORD}" psql \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d "${DB_NAME}" \
        -t -A -c "${query}"
}

# Check database retention policies
check_database_retention() {
    log "Checking database retention policies"
    
    # Check jobs table for old records
    local cutoff_date=$(date -d "${RETENTION_DAYS} days ago" '+%Y-%m-%d')
    
    local old_jobs=$(query_db "SELECT COUNT(*) FROM jobs WHERE created_at < '${cutoff_date}'")
    local old_artifacts=$(query_db "SELECT COUNT(*) FROM artifacts WHERE created_at < '${cutoff_date}'")
    
    if [[ ${old_jobs} -gt 0 ]]; then
        log "WARNING: Found ${old_jobs} jobs older than ${RETENTION_DAYS} days"
        return 1
    fi
    
    if [[ ${old_artifacts} -gt 0 ]]; then
        log "WARNING: Found ${old_artifacts} artifacts older than ${RETENTION_DAYS} days"
        return 1
    fi
    
    # Check recent cleanup activity
    local cleanup_count=$(query_db "SELECT COUNT(*) FROM jobs WHERE status = 'deleted' AND updated_at > NOW() - INTERVAL '7 days'")
    
    log "Database retention check passed"
    log "  Old jobs: ${old_jobs}"
    log "  Old artifacts: ${old_artifacts}"
    log "  Recent cleanups: ${cleanup_count}"
    
    return 0
}

# Check S3/R2 storage retention
check_storage_retention() {
    log "Checking storage retention policies"
    
    if ! command -v aws >/dev/null 2>&1; then
        log "WARNING: AWS CLI not available, skipping storage check"
        return 1
    fi
    
    local bucket="${R2_BUCKET:-oneshot-prod-storage}"
    local cutoff_date=$(date -d "${RETENTION_DAYS} days ago" '+%Y-%m-%d')
    
    # List objects older than retention period
    local old_objects=$(aws s3api list-objects-v2 \
        --bucket "${bucket}" \
        --query "Contents[?LastModified<='${cutoff_date}T23:59:59.999Z']" \
        --output json | jq '. | length')
    
    if [[ ${old_objects} -gt 0 ]]; then
        log "WARNING: Found ${old_objects} storage objects older than ${RETENTION_DAYS} days"
        
        # List some examples
        aws s3api list-objects-v2 \
            --bucket "${bucket}" \
            --query "Contents[?LastModified<='${cutoff_date}T23:59:59.999Z'][:5].[Key,LastModified]" \
            --output table | head -10 | while read line; do
            log "  Example old object: ${line}"
        done
        
        return 1
    fi
    
    log "Storage retention check passed"
    log "  Old objects: ${old_objects}"
    
    return 0
}

# Check retention job logs
check_retention_jobs() {
    log "Checking retention job execution"
    
    # Check if retention job has run recently (within 25 hours for daily job)
    local retention_log="/var/log/data-retention.log"
    
    if [[ ! -f "${retention_log}" ]]; then
        log "WARNING: Retention job log not found: ${retention_log}"
        return 1
    fi
    
    # Check for recent successful runs
    local recent_success=$(grep -c "Retention cleanup completed successfully" "${retention_log}" 2>/dev/null | tail -5 | wc -l)
    local last_run=$(grep "Retention cleanup completed" "${retention_log}" 2>/dev/null | tail -1 | awk '{print $1, $2}')
    
    if [[ -z "${last_run}" ]]; then
        log "WARNING: No retention job completion found in logs"
        return 1
    fi
    
    # Check if last run was within 25 hours
    local last_run_timestamp=$(date -d "${last_run}" +%s 2>/dev/null || echo "0")
    local current_timestamp=$(date +%s)
    local hours_since_last_run=$(( (current_timestamp - last_run_timestamp) / 3600 ))
    
    if [[ ${hours_since_last_run} -gt 25 ]]; then
        log "WARNING: Last retention job run was ${hours_since_last_run} hours ago"
        log "  Last run: ${last_run}"
        return 1
    fi
    
    log "Retention job check passed"
    log "  Last successful run: ${last_run}"
    log "  Hours since last run: ${hours_since_last_run}"
    log "  Recent successful runs: ${recent_success}"
    
    return 0
}

# Check cron job configuration
check_cron_configuration() {
    log "Checking cron job configuration"
    
    # Check if retention cron job is configured
    local cron_entry=$(crontab -l 2>/dev/null | grep -E "(retention|cleanup)" || echo "")
    
    if [[ -z "${cron_entry}" ]]; then
        log "WARNING: No retention cron job found"
        return 1
    fi
    
    log "Cron configuration check passed"
    log "  Cron entry: ${cron_entry}"
    
    return 0
}

# Check disk space and growth trends
check_disk_usage() {
    log "Checking disk usage trends"
    
    local backup_dir="${BACKUP_DIR:-/backups}"
    local data_dir="${DATA_DIR:-/var/lib/postgresql/data}"
    
    # Check current disk usage
    if [[ -d "${backup_dir}" ]]; then
        local backup_usage=$(du -sh "${backup_dir}" | cut -f1)
        log "  Backup directory usage: ${backup_usage}"
    fi
    
    if [[ -d "${data_dir}" ]]; then
        local data_usage=$(du -sh "${data_dir}" | cut -f1)
        log "  Data directory usage: ${data_usage}"
    fi
    
    # Check available space
    local available_space=$(df -h / | awk 'NR==2 {print $4}')
    local usage_percent=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
    
    log "  Root filesystem available: ${available_space} (${usage_percent}% used)"
    
    if [[ ${usage_percent} -gt 90 ]]; then
        log "WARNING: Disk usage is ${usage_percent}%, consider increasing retention frequency"
        return 1
    fi
    
    return 0
}

# Main verification function
main() {
    log "Starting retention verification"
    
    local exit_code=0
    
    # Run all checks
    check_database_retention || exit_code=1
    check_storage_retention || exit_code=1
    check_retention_jobs || exit_code=1
    check_cron_configuration || exit_code=1
    check_disk_usage || exit_code=1
    
    if [[ ${exit_code} -eq 0 ]]; then
        log "✓ All retention checks passed"
    else
        log "✗ Some retention checks failed"
    fi
    
    # Send notification if webhook configured
    if [[ -n "${BACKUP_WEBHOOK_URL:-}" ]]; then
        local status="success"
        if [[ ${exit_code} -ne 0 ]]; then
            status="warning"
        fi
        
        curl -X POST "${BACKUP_WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "{
                \"status\": \"${status}\",
                \"operation\": \"retention_verification\",
                \"timestamp\": \"$(date -Iseconds)\"
            }" \
            --silent --fail || log "WARNING: Webhook notification failed"
    fi
    
    log "Retention verification completed"
    exit ${exit_code}
}

# Run main function
main "$@"