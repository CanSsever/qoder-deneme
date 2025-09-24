#!/bin/bash

# R2/S3 Storage Lifecycle Management Script
# Manages backup retention and storage class transitions

set -euo pipefail

# Configuration
R2_BUCKET="${R2_BUCKET:-oneshot-prod-storage}"
BACKUP_BUCKET="${S3_BACKUP_BUCKET:-oneshot-prod-backups}"
TEMP_DIR="${TEMP_DIR:-/tmp/r2-backup}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Retention policies (days)
DAILY_RETENTION=7
WEEKLY_RETENTION=30
MONTHLY_RETENTION=90
ARCHIVE_RETENTION=365

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "/var/log/r2-lifecycle.log"
}

# Validate AWS CLI configuration
validate_aws_config() {
    if ! command -v aws >/dev/null 2>&1; then
        log "ERROR: AWS CLI not installed"
        exit 1
    fi
    
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        log "ERROR: AWS credentials not configured"
        exit 1
    fi
    
    log "AWS configuration validated"
}

# Create R2 backup snapshot
create_r2_backup() {
    local backup_name="r2-backup-${TIMESTAMP}"
    
    log "Creating R2 storage backup: ${backup_name}"
    
    mkdir -p "${TEMP_DIR}"
    
    # Sync R2 content to backup bucket
    aws s3 sync "s3://${R2_BUCKET}/" "s3://${BACKUP_BUCKET}/r2-snapshots/${backup_name}/" \
        --storage-class STANDARD_IA \
        --exclude "*.tmp" \
        --exclude "*/.DS_Store" \
        --delete \
        --exact-timestamps
    
    if [[ $? -eq 0 ]]; then
        log "R2 backup completed: ${backup_name}"
        
        # Create manifest
        aws s3api list-objects-v2 \
            --bucket "${BACKUP_BUCKET}" \
            --prefix "r2-snapshots/${backup_name}/" \
            --output json > "${TEMP_DIR}/manifest-${backup_name}.json"
        
        aws s3 cp "${TEMP_DIR}/manifest-${backup_name}.json" \
            "s3://${BACKUP_BUCKET}/r2-snapshots/${backup_name}/manifest.json"
        
        rm -f "${TEMP_DIR}/manifest-${backup_name}.json"
    else
        log "ERROR: R2 backup failed"
        return 1
    fi
}

# Apply lifecycle transitions
apply_lifecycle_policy() {
    log "Applying storage lifecycle policies"
    
    local cutoff_date_7d=$(date -d '7 days ago' '+%Y-%m-%d')
    local cutoff_date_30d=$(date -d '30 days ago' '+%Y-%m-%d')
    local cutoff_date_90d=$(date -d '90 days ago' '+%Y-%m-%d')
    local cutoff_date_365d=$(date -d '365 days ago' '+%Y-%m-%d')
    
    # Move 7+ day old daily backups to IA
    log "Transitioning daily backups to IA (7+ days old)"
    aws s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --prefix "daily/" \
        --query "Contents[?LastModified<=\`${cutoff_date_7d}\`].[Key]" \
        --output text | while read -r key; do
        
        if [[ -n "${key}" && "${key}" != "None" ]]; then
            aws s3 cp "s3://${BACKUP_BUCKET}/${key}" "s3://${BACKUP_BUCKET}/${key}" \
                --storage-class STANDARD_IA \
                --metadata-directive REPLACE >/dev/null 2>&1
        fi
    done
    
    # Move 30+ day old backups to Glacier
    log "Transitioning backups to Glacier (30+ days old)"
    aws s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --query "Contents[?LastModified<=\`${cutoff_date_30d}\` && StorageClass!=\`GLACIER\`].[Key]" \
        --output text | while read -r key; do
        
        if [[ -n "${key}" && "${key}" != "None" ]]; then
            aws s3 cp "s3://${BACKUP_BUCKET}/${key}" "s3://${BACKUP_BUCKET}/${key}" \
                --storage-class GLACIER \
                --metadata-directive REPLACE >/dev/null 2>&1
        fi
    done
    
    # Move 90+ day old backups to Deep Archive
    log "Transitioning backups to Deep Archive (90+ days old)"
    aws s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --query "Contents[?LastModified<=\`${cutoff_date_90d}\` && StorageClass!=\`DEEP_ARCHIVE\`].[Key]" \
        --output text | while read -r key; do
        
        if [[ -n "${key}" && "${key}" != "None" ]]; then
            aws s3 cp "s3://${BACKUP_BUCKET}/${key}" "s3://${BACKUP_BUCKET}/${key}" \
                --storage-class DEEP_ARCHIVE \
                --metadata-directive REPLACE >/dev/null 2>&1
        fi
    done
    
    log "Lifecycle transitions completed"
}

# Cleanup expired backups
cleanup_expired_backups() {
    log "Cleaning up expired backups (${ARCHIVE_RETENTION}+ days old)"
    
    local cutoff_date=$(date -d "${ARCHIVE_RETENTION} days ago" '+%Y-%m-%d')
    
    # List and delete expired objects
    aws s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --query "Contents[?LastModified<=\`${cutoff_date}\`].[Key]" \
        --output text | while read -r key; do
        
        if [[ -n "${key}" && "${key}" != "None" ]]; then
            aws s3 rm "s3://${BACKUP_BUCKET}/${key}"
            log "Deleted expired backup: ${key}"
        fi
    done
}

# Verify backup integrity
verify_backups() {
    log "Verifying recent backup integrity"
    
    # Check last 3 daily backups
    local recent_backups=$(aws s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --prefix "daily/" \
        --query "reverse(sort_by(Contents, &LastModified))[:3].[Key]" \
        --output text)
    
    local verified_count=0
    
    while IFS= read -r backup_key; do
        if [[ -n "${backup_key}" && "${backup_key}" != "None" ]]; then
            # Check if backup exists and has content
            local size=$(aws s3api head-object \
                --bucket "${BACKUP_BUCKET}" \
                --key "${backup_key}" \
                --query "ContentLength" \
                --output text 2>/dev/null || echo "0")
            
            if [[ ${size} -gt 0 ]]; then
                log "Verified backup: ${backup_key} (${size} bytes)"
                ((verified_count++))
            else
                log "WARNING: Empty or missing backup: ${backup_key}"
            fi
        fi
    done <<< "${recent_backups}"
    
    log "Verified ${verified_count} recent backups"
    
    if [[ ${verified_count} -eq 0 ]]; then
        log "ERROR: No valid recent backups found"
        return 1
    fi
}

# Generate storage report
generate_storage_report() {
    log "Generating storage usage report"
    
    local report_file="/tmp/storage-report-${TIMESTAMP}.json"
    
    # Get bucket size by storage class
    aws s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --output json > "${report_file}"
    
    local total_objects=$(jq '.KeyCount // 0' "${report_file}")
    local total_size=$(jq '[.Contents[]?.Size] | add // 0' "${report_file}")
    local standard_size=$(jq '[.Contents[] | select(.StorageClass == "STANDARD" or .StorageClass == null)?.Size] | add // 0' "${report_file}")
    local ia_size=$(jq '[.Contents[] | select(.StorageClass == "STANDARD_IA")?.Size] | add // 0' "${report_file}")
    local glacier_size=$(jq '[.Contents[] | select(.StorageClass == "GLACIER")?.Size] | add // 0' "${report_file}")
    local deep_archive_size=$(jq '[.Contents[] | select(.StorageClass == "DEEP_ARCHIVE")?.Size] | add // 0' "${report_file}")
    
    log "Storage Report:"
    log "  Total Objects: ${total_objects}"
    log "  Total Size: $(numfmt --to=iec ${total_size}) bytes"
    log "  Standard: $(numfmt --to=iec ${standard_size}) bytes"
    log "  Standard-IA: $(numfmt --to=iec ${ia_size}) bytes"
    log "  Glacier: $(numfmt --to=iec ${glacier_size}) bytes"
    log "  Deep Archive: $(numfmt --to=iec ${deep_archive_size}) bytes"
    
    # Upload report to S3
    aws s3 cp "${report_file}" "s3://${BACKUP_BUCKET}/reports/storage-report-${TIMESTAMP}.json"
    rm -f "${report_file}"
}

# Main execution
main() {
    log "Starting R2 lifecycle management"
    
    validate_aws_config
    
    # Create backup if it's backup day (configurable)
    if [[ "${1:-}" == "backup" ]] || [[ $(date +%u) -eq 1 ]]; then  # Monday
        create_r2_backup
    fi
    
    apply_lifecycle_policy
    cleanup_expired_backups
    verify_backups
    generate_storage_report
    
    log "R2 lifecycle management completed"
    
    # Send notification
    if [[ -n "${BACKUP_WEBHOOK_URL:-}" ]]; then
        curl -X POST "${BACKUP_WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "{
                \"status\": \"success\",
                \"operation\": \"r2_lifecycle\",
                \"timestamp\": \"${TIMESTAMP}\"
            }" \
            --silent --fail || log "WARNING: Webhook notification failed"
    fi
}

# Run main function
main "$@"