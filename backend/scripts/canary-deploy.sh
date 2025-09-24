#!/bin/bash

# Production Canary Deployment Script
# Implements 10% → monitor → 100% deployment strategy with rollback

set -euo pipefail

# Configuration
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-oneshot-api}"
NAMESPACE="${NAMESPACE:-production}"
CANARY_PERCENTAGE="${CANARY_PERCENTAGE:-10}"
MONITORING_DURATION="${MONITORING_DURATION:-300}"  # 5 minutes
HEALTH_CHECK_INTERVAL=30
MAX_ERROR_RATE=0.05  # 5%
MAX_LATENCY_P95=2000  # 2 seconds
ROLLBACK_ON_FAILURE="${ROLLBACK_ON_FAILURE:-true}"

# Prometheus/monitoring endpoints
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://grafana:3000}"

# Logging
LOG_FILE="/var/log/canary-deployment.log"
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Error handling
cleanup() {
    if [[ "${ROLLBACK_ON_FAILURE}" == "true" && "${1:-}" == "error" ]]; then
        log "ERROR detected, initiating rollback"
        rollback_deployment
    fi
}
trap 'cleanup error' ERR

# Get current deployment status
get_deployment_status() {
    kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" -o json 2>/dev/null || echo "{}"
}

# Check if deployment exists
deployment_exists() {
    kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" >/dev/null 2>&1
}

# Get current image tag
get_current_image() {
    kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" \
        -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo ""
}

# Update deployment with new image
update_deployment_image() {
    local new_image="$1"
    log "Updating deployment image to: ${new_image}"
    
    kubectl set image deployment/"${DEPLOYMENT_NAME}" \
        "${DEPLOYMENT_NAME}"="${new_image}" \
        -n "${NAMESPACE}"
    
    # Wait for rollout to start
    kubectl rollout status deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=60s
}

# Scale deployment to specific replica count
scale_deployment() {
    local replicas="$1"
    log "Scaling deployment to ${replicas} replicas"
    
    kubectl scale deployment "${DEPLOYMENT_NAME}" --replicas="${replicas}" -n "${NAMESPACE}"
    kubectl rollout status deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=300s
}

# Implement canary deployment using multiple deployments
deploy_canary() {
    local new_image="$1"
    local canary_name="${DEPLOYMENT_NAME}-canary"
    
    log "Starting canary deployment with ${CANARY_PERCENTAGE}% traffic"
    
    # Create canary deployment
    kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" -o yaml | \
        sed "s/${DEPLOYMENT_NAME}/${canary_name}/g" | \
        sed "s/replicas: [0-9]*/replicas: 1/" | \
        kubectl apply -f -
    
    # Update canary with new image
    kubectl set image deployment/"${canary_name}" \
        "${DEPLOYMENT_NAME}"="${new_image}" \
        -n "${NAMESPACE}"
    
    # Wait for canary to be ready
    kubectl rollout status deployment/"${canary_name}" -n "${NAMESPACE}" --timeout=300s
    
    # Update service to include canary (weight-based routing would be done via Istio/Linkerd)
    # For simplicity, we'll use label selectors and assume external load balancer handles weights
    kubectl patch service "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --type='merge' \
        -p '{"spec":{"selector":{"app":"'${DEPLOYMENT_NAME}'","version":"canary"}}}'
    
    log "Canary deployment created successfully"
    return 0
}

# Check application health
check_app_health() {
    local service_url="${SERVICE_URL:-http://${DEPLOYMENT_NAME}.${NAMESPACE}.svc.cluster.local}"
    
    log "Checking application health: ${service_url}/health"
    
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" "${service_url}/health" || echo "000")
    
    if [[ "${response_code}" == "200" ]]; then
        log "✓ Health check passed (${response_code})"
        return 0
    else
        log "✗ Health check failed (${response_code})"
        return 1
    fi
}

# Query Prometheus metrics
query_prometheus() {
    local query="$1"
    local result=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=${query}" | \
        jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0")
    echo "${result}"
}

# Monitor deployment metrics
monitor_metrics() {
    local duration="$1"
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    
    log "Monitoring metrics for ${duration} seconds"
    
    while [[ $(date +%s) -lt ${end_time} ]]; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        # Check error rate
        local error_rate=$(query_prometheus "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m])")
        
        # Check P95 latency
        local p95_latency=$(query_prometheus "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))")
        
        # Check if we can convert to numbers (handle empty responses)
        error_rate=${error_rate:-0}
        p95_latency=${p95_latency:-0}
        
        log "Metrics at ${elapsed}s: Error rate: ${error_rate}, P95 latency: ${p95_latency}s"
        
        # Convert to numbers for comparison
        local error_rate_num=$(echo "${error_rate}" | awk '{print $1 + 0}')
        local p95_latency_ms=$(echo "${p95_latency} * 1000" | bc -l 2>/dev/null | awk '{print int($1)}' || echo "0")
        
        # Check thresholds
        if (( $(echo "${error_rate_num} > ${MAX_ERROR_RATE}" | bc -l) )); then
            log "ERROR: Error rate ${error_rate} exceeds threshold ${MAX_ERROR_RATE}"
            return 1
        fi
        
        if [[ ${p95_latency_ms} -gt ${MAX_LATENCY_P95} ]]; then
            log "ERROR: P95 latency ${p95_latency_ms}ms exceeds threshold ${MAX_LATENCY_P95}ms"
            return 1
        fi
        
        # Health check
        if ! check_app_health; then
            log "ERROR: Health check failed during monitoring"
            return 1
        fi
        
        sleep "${HEALTH_CHECK_INTERVAL}"
    done
    
    log "✓ Monitoring completed successfully"
    return 0
}

# Promote canary to 100%
promote_canary() {
    local canary_name="${DEPLOYMENT_NAME}-canary"
    local new_image=$(kubectl get deployment "${canary_name}" -n "${NAMESPACE}" \
        -o jsonpath='{.spec.template.spec.containers[0].image}')
    
    log "Promoting canary to 100%: ${new_image}"
    
    # Update main deployment with canary image
    kubectl set image deployment/"${DEPLOYMENT_NAME}" \
        "${DEPLOYMENT_NAME}"="${new_image}" \
        -n "${NAMESPACE}"
    
    # Wait for rollout
    kubectl rollout status deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=600s
    
    # Remove canary deployment
    kubectl delete deployment "${canary_name}" -n "${NAMESPACE}" || true
    
    # Restore service selector to main deployment
    kubectl patch service "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --type='merge' \
        -p '{"spec":{"selector":{"app":"'${DEPLOYMENT_NAME}'"}}}'
    
    log "✓ Canary promoted successfully"
}

# Rollback deployment
rollback_deployment() {
    log "Rolling back deployment"
    
    # Delete canary if exists
    local canary_name="${DEPLOYMENT_NAME}-canary"
    kubectl delete deployment "${canary_name}" -n "${NAMESPACE}" || true
    
    # Rollback main deployment
    kubectl rollout undo deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}"
    kubectl rollout status deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout=300s
    
    # Restore service selector
    kubectl patch service "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --type='merge' \
        -p '{"spec":{"selector":{"app":"'${DEPLOYMENT_NAME}'"}}}'
    
    log "✓ Rollback completed"
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    
    if [[ -n "${WEBHOOK_URL:-}" ]]; then
        curl -X POST "${WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "{
                \"status\": \"${status}\",
                \"message\": \"${message}\",
                \"deployment\": \"${DEPLOYMENT_NAME}\",
                \"namespace\": \"${NAMESPACE}\",
                \"timestamp\": \"$(date -Iseconds)\"
            }" \
            --silent --fail || log "WARNING: Notification failed"
    fi
}

# Generate deployment report
generate_report() {
    local status="$1"
    local deployment_time="$2"
    
    local report_file="/tmp/canary-deployment-$(date +%Y%m%d_%H%M%S).json"
    
    cat > "${report_file}" <<EOF
{
  "deployment": "${DEPLOYMENT_NAME}",
  "namespace": "${NAMESPACE}",
  "status": "${status}",
  "deployment_time": ${deployment_time},
  "canary_percentage": ${CANARY_PERCENTAGE},
  "monitoring_duration": ${MONITORING_DURATION},
  "timestamp": "$(date -Iseconds)",
  "image": "$(get_current_image)",
  "metrics": {
    "max_error_rate": ${MAX_ERROR_RATE},
    "max_latency_p95": ${MAX_LATENCY_P95}
  }
}
EOF
    
    log "Deployment report saved: ${report_file}"
    
    # Upload to S3 if configured
    if [[ -n "${S3_REPORTS_BUCKET:-}" ]] && command -v aws >/dev/null 2>&1; then
        aws s3 cp "${report_file}" "s3://${S3_REPORTS_BUCKET}/deployments/"
        log "Report uploaded to S3"
    fi
}

# Main deployment function
main() {
    local new_image="$1"
    local start_time=$(date +%s)
    
    log "Starting canary deployment"
    log "Target image: ${new_image}"
    log "Current image: $(get_current_image)"
    
    # Validate prerequisites
    if ! deployment_exists; then
        log "ERROR: Deployment ${DEPLOYMENT_NAME} not found in namespace ${NAMESPACE}"
        exit 1
    fi
    
    if ! command -v kubectl >/dev/null 2>&1; then
        log "ERROR: kubectl not found"
        exit 1
    fi
    
    # Phase 1: Deploy canary
    log "Phase 1: Deploying canary (${CANARY_PERCENTAGE}%)"
    if ! deploy_canary "${new_image}"; then
        log "ERROR: Canary deployment failed"
        send_notification "failed" "Canary deployment failed"
        exit 1
    fi
    
    # Phase 2: Monitor canary
    log "Phase 2: Monitoring canary for ${MONITORING_DURATION} seconds"
    if ! monitor_metrics "${MONITORING_DURATION}"; then
        log "ERROR: Monitoring failed, rolling back"
        send_notification "failed" "Canary monitoring failed, rolled back"
        rollback_deployment
        exit 1
    fi
    
    # Phase 3: Promote to 100%
    log "Phase 3: Promoting canary to 100%"
    if ! promote_canary; then
        log "ERROR: Promotion failed, rolling back"
        send_notification "failed" "Canary promotion failed, rolled back"
        rollback_deployment
        exit 1
    fi
    
    # Success
    local deployment_time=$(($(date +%s) - start_time))
    log "✅ Canary deployment completed successfully in ${deployment_time} seconds"
    
    send_notification "success" "Canary deployment completed successfully"
    generate_report "success" "${deployment_time}"
}

# Usage information
usage() {
    echo "Usage: $0 <new-image-tag>"
    echo "Example: $0 myapp:v1.2.3"
    echo ""
    echo "Environment variables:"
    echo "  DEPLOYMENT_NAME (default: oneshot-api)"
    echo "  NAMESPACE (default: production)"
    echo "  CANARY_PERCENTAGE (default: 10)"
    echo "  MONITORING_DURATION (default: 300)"
    echo "  MAX_ERROR_RATE (default: 0.05)"
    echo "  MAX_LATENCY_P95 (default: 2000)"
    echo "  ROLLBACK_ON_FAILURE (default: true)"
}

# Script entry point
if [[ $# -eq 0 ]]; then
    usage
    exit 1
fi

if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    usage
    exit 0
fi

if [[ "$1" == "--rollback" ]]; then
    log "Manual rollback requested"
    rollback_deployment
    exit 0
fi

main "$1"