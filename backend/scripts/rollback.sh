#!/bin/bash

# Production Rollback Script
# Quick rollback with validation and monitoring

set -euo pipefail

# Configuration
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-oneshot-api}"
NAMESPACE="${NAMESPACE:-production}"
ROLLBACK_TIMEOUT="${ROLLBACK_TIMEOUT:-300}"
VALIDATION_CHECKS="${VALIDATION_CHECKS:-true}"

# Logging
LOG_FILE="/var/log/rollback.log"
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Error handling
trap 'log "ERROR: Rollback script failed"; exit 1' ERR

# Get deployment history
get_deployment_history() {
    kubectl rollout history deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}"
}

# Get current revision
get_current_revision() {
    kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" \
        -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}'
}

# Get previous revision
get_previous_revision() {
    local current_rev=$(get_current_revision)
    local prev_rev=$((current_rev - 1))
    
    if [[ ${prev_rev} -lt 1 ]]; then
        log "ERROR: No previous revision available"
        exit 1
    fi
    
    echo "${prev_rev}"
}

# Validate rollback target
validate_rollback_target() {
    local target_revision="$1"
    
    log "Validating rollback target revision: ${target_revision}"
    
    # Check if revision exists
    if ! kubectl rollout history deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}" \
        --revision="${target_revision}" >/dev/null 2>&1; then
        log "ERROR: Revision ${target_revision} not found"
        return 1
    fi
    
    # Get revision details
    local revision_info=$(kubectl rollout history deployment/"${DEPLOYMENT_NAME}" \
        -n "${NAMESPACE}" --revision="${target_revision}")
    
    log "Rollback target details:"
    echo "${revision_info}" | while read line; do
        log "  ${line}"
    done
    
    return 0
}

# Perform rollback
perform_rollback() {
    local target_revision="${1:-}"
    
    log "Starting rollback"
    
    if [[ -n "${target_revision}" ]]; then
        log "Rolling back to revision: ${target_revision}"
        kubectl rollout undo deployment/"${DEPLOYMENT_NAME}" \
            -n "${NAMESPACE}" --to-revision="${target_revision}"
    else
        log "Rolling back to previous revision"
        kubectl rollout undo deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}"
    fi
    
    # Wait for rollback to complete
    log "Waiting for rollback to complete (timeout: ${ROLLBACK_TIMEOUT}s)"
    kubectl rollout status deployment/"${DEPLOYMENT_NAME}" \
        -n "${NAMESPACE}" --timeout="${ROLLBACK_TIMEOUT}s"
    
    log "✓ Rollback completed"
}

# Validate rollback
validate_rollback() {
    log "Validating rollback"
    
    # Check deployment status
    local ready_replicas=$(kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired_replicas=$(kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" \
        -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [[ "${ready_replicas}" != "${desired_replicas}" ]]; then
        log "ERROR: Deployment not fully ready (${ready_replicas}/${desired_replicas})"
        return 1
    fi
    
    # Health check
    local service_url="${SERVICE_URL:-http://${DEPLOYMENT_NAME}.${NAMESPACE}.svc.cluster.local}"
    local max_attempts=10
    local attempt=1
    
    while [[ ${attempt} -le ${max_attempts} ]]; do
        log "Health check attempt ${attempt}/${max_attempts}"
        
        local response_code=$(curl -s -o /dev/null -w "%{http_code}" \
            "${service_url}/health" 2>/dev/null || echo "000")
        
        if [[ "${response_code}" == "200" ]]; then
            log "✓ Health check passed"
            break
        elif [[ ${attempt} -eq ${max_attempts} ]]; then
            log "ERROR: Health check failed after ${max_attempts} attempts"
            return 1
        else
            log "Health check failed (${response_code}), retrying in 10s..."
            sleep 10
        fi
        
        ((attempt++))
    done
    
    # Additional validation checks
    if [[ "${VALIDATION_CHECKS}" == "true" ]]; then
        # Check for any failing pods
        local failing_pods=$(kubectl get pods -n "${NAMESPACE}" \
            -l app="${DEPLOYMENT_NAME}" \
            --field-selector=status.phase!=Running \
            -o name 2>/dev/null | wc -l)
        
        if [[ ${failing_pods} -gt 0 ]]; then
            log "WARNING: ${failing_pods} pods are not in Running state"
            kubectl get pods -n "${NAMESPACE}" -l app="${DEPLOYMENT_NAME}"
        fi
        
        # Check recent events
        log "Recent events:"
        kubectl get events -n "${NAMESPACE}" \
            --field-selector involvedObject.name="${DEPLOYMENT_NAME}" \
            --sort-by='.lastTimestamp' | tail -5 | while read line; do
            log "  ${line}"
        done
    fi
    
    log "✓ Rollback validation completed"
    return 0
}

# Generate rollback report
generate_rollback_report() {
    local status="$1"
    local rollback_time="$2"
    local from_revision="$3"
    local to_revision="$4"
    
    local report_file="/tmp/rollback-$(date +%Y%m%d_%H%M%S).json"
    
    cat > "${report_file}" <<EOF
{
  "deployment": "${DEPLOYMENT_NAME}",
  "namespace": "${NAMESPACE}",
  "status": "${status}",
  "rollback_time": ${rollback_time},
  "from_revision": "${from_revision}",
  "to_revision": "${to_revision}",
  "timestamp": "$(date -Iseconds)",
  "current_image": "$(kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo 'unknown')",
  "ready_replicas": $(kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)
}
EOF
    
    log "Rollback report saved: ${report_file}"
    
    # Upload to S3 if configured
    if [[ -n "${S3_REPORTS_BUCKET:-}" ]] && command -v aws >/dev/null 2>&1; then
        aws s3 cp "${report_file}" "s3://${S3_REPORTS_BUCKET}/rollbacks/"
        log "Report uploaded to S3"
    fi
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    local from_revision="$3"
    local to_revision="$4"
    
    if [[ -n "${WEBHOOK_URL:-}" ]]; then
        curl -X POST "${WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "{
                \"status\": \"${status}\",
                \"message\": \"${message}\",
                \"deployment\": \"${DEPLOYMENT_NAME}\",
                \"namespace\": \"${NAMESPACE}\",
                \"from_revision\": \"${from_revision}\",
                \"to_revision\": \"${to_revision}\",
                \"timestamp\": \"$(date -Iseconds)\"
            }" \
            --silent --fail || log "WARNING: Notification failed"
    fi
}

# Main rollback function
main() {
    local target_revision="${1:-}"
    local start_time=$(date +%s)
    
    log "Starting rollback process"
    
    # Validate prerequisites
    if ! kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" >/dev/null 2>&1; then
        log "ERROR: Deployment ${DEPLOYMENT_NAME} not found in namespace ${NAMESPACE}"
        exit 1
    fi
    
    if ! command -v kubectl >/dev/null 2>&1; then
        log "ERROR: kubectl not found"
        exit 1
    fi
    
    # Get current state
    local current_revision=$(get_current_revision)
    local rollback_to_revision
    
    if [[ -n "${target_revision}" ]]; then
        rollback_to_revision="${target_revision}"
        validate_rollback_target "${target_revision}"
    else
        rollback_to_revision=$(get_previous_revision)
        log "Auto-detected previous revision: ${rollback_to_revision}"
    fi
    
    log "Current revision: ${current_revision}"
    log "Rolling back to revision: ${rollback_to_revision}"
    
    # Show deployment history
    log "Deployment history:"
    get_deployment_history | while read line; do
        log "  ${line}"
    done
    
    # Confirm rollback in interactive mode
    if [[ "${INTERACTIVE:-false}" == "true" && -t 0 ]]; then
        echo "Proceed with rollback? (y/N)"
        read -r confirm
        if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
            log "Rollback cancelled by user"
            exit 0
        fi
    fi
    
    # Perform rollback
    if ! perform_rollback "${target_revision}"; then
        log "ERROR: Rollback failed"
        send_notification "failed" "Rollback failed" "${current_revision}" "${rollback_to_revision}"
        exit 1
    fi
    
    # Validate rollback
    if ! validate_rollback; then
        log "ERROR: Rollback validation failed"
        send_notification "failed" "Rollback validation failed" "${current_revision}" "${rollback_to_revision}"
        exit 1
    fi
    
    # Success
    local rollback_time=$(($(date +%s) - start_time))
    log "✅ Rollback completed successfully in ${rollback_time} seconds"
    
    send_notification "success" "Rollback completed successfully" "${current_revision}" "${rollback_to_revision}"
    generate_rollback_report "success" "${rollback_time}" "${current_revision}" "${rollback_to_revision}"
}

# Usage information
usage() {
    echo "Usage: $0 [revision-number]"
    echo "Example: $0 5"
    echo "Example: $0    # rollback to previous revision"
    echo ""
    echo "Environment variables:"
    echo "  DEPLOYMENT_NAME (default: oneshot-api)"
    echo "  NAMESPACE (default: production)"
    echo "  ROLLBACK_TIMEOUT (default: 300)"
    echo "  VALIDATION_CHECKS (default: true)"
    echo "  INTERACTIVE (default: false)"
}

# Script entry point
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

if [[ "${1:-}" == "--history" ]]; then
    get_deployment_history
    exit 0
fi

main "${1:-}"