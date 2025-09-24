#!/bin/bash

# Production Smoke Test Runner
# Executes comprehensive smoke tests using Newman (Postman CLI)

set -euo pipefail

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
COLLECTION_FILE="${COLLECTION_FILE:-tests/smoke/oneshot-smoke-tests.postman_collection.json}"
ENV_FILE="${ENV_FILE:-tests/smoke/environments/${ENVIRONMENT}.postman_environment.json}"
OUTPUT_DIR="${OUTPUT_DIR:-/tmp/smoke-tests}"
REPORT_FORMAT="${REPORT_FORMAT:-htmlextra,json,cli}"
TIMEOUT="${TIMEOUT:-30000}"
DELAY_REQUEST="${DELAY_REQUEST:-500}"
BAIL="${BAIL:-false}"

# Logging
LOG_FILE="${OUTPUT_DIR}/smoke-test.log"
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Error handling
cleanup() {
    if [[ "${SEND_NOTIFICATIONS:-true}" == "true" && "${1:-}" == "error" ]]; then
        send_notification "failed" "Smoke tests failed in ${ENVIRONMENT} environment"
    fi
}
trap 'cleanup error' ERR

# Setup function
setup() {
    log "Setting up smoke test environment"
    
    # Create output directory
    mkdir -p "${OUTPUT_DIR}"
    
    # Check if newman is installed
    if ! command -v newman >/dev/null 2>&1; then
        log "Installing Newman CLI..."
        npm install -g newman newman-reporter-htmlextra
    fi
    
    # Validate test files exist
    if [[ ! -f "${COLLECTION_FILE}" ]]; then
        log "ERROR: Collection file not found: ${COLLECTION_FILE}"
        exit 1
    fi
    
    if [[ ! -f "${ENV_FILE}" ]]; then
        log "ERROR: Environment file not found: ${ENV_FILE}"
        exit 1
    fi
    
    log "Newman version: $(newman --version)"
}

# Pre-test validation
pre_test_validation() {
    log "Running pre-test validation"
    
    # Extract base URL from environment file
    local base_url=$(jq -r '.values[] | select(.key=="base_url") | .value' "${ENV_FILE}")
    
    log "Testing connectivity to: ${base_url}"
    
    # Basic connectivity test
    if ! curl -s --max-time 10 "${base_url}/health" >/dev/null 2>&1; then
        log "ERROR: Cannot reach ${base_url}/health"
        exit 1
    fi
    
    log "✓ Connectivity test passed"
}

# Run smoke tests
run_smoke_tests() {
    log "Starting smoke tests for ${ENVIRONMENT} environment"
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local report_name="smoke-test-${ENVIRONMENT}-${timestamp}"
    
    # Newman options
    local newman_opts=(
        run "${COLLECTION_FILE}"
        --environment "${ENV_FILE}"
        --reporters "${REPORT_FORMAT}"
        --reporter-htmlextra-export "${OUTPUT_DIR}/${report_name}.html"
        --reporter-json-export "${OUTPUT_DIR}/${report_name}.json"
        --timeout-request "${TIMEOUT}"
        --delay-request "${DELAY_REQUEST}"
        --color on
        --verbose
    )
    
    # Add bail option if enabled
    if [[ "${BAIL}" == "true" ]]; then
        newman_opts+=(--bail)
    fi
    
    # Add global variables if specified
    if [[ -n "${NEWMAN_GLOBALS:-}" ]]; then
        newman_opts+=(--globals "${NEWMAN_GLOBALS}")
    fi
    
    log "Newman command: newman ${newman_opts[*]}"
    
    # Run tests
    local start_time=$(date +%s)
    local exit_code=0
    
    newman "${newman_opts[@]}" 2>&1 | tee -a "${LOG_FILE}" || exit_code=$?
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ ${exit_code} -eq 0 ]]; then
        log "✅ Smoke tests completed successfully in ${duration} seconds"
    else
        log "❌ Smoke tests failed with exit code ${exit_code} after ${duration} seconds"
    fi
    
    return ${exit_code}
}

# Generate summary report
generate_summary() {
    local test_result="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    
    log "Generating test summary"
    
    # Find the latest JSON report
    local json_report=$(ls -t "${OUTPUT_DIR}"/smoke-test-${ENVIRONMENT}-*.json 2>/dev/null | head -1)
    
    if [[ -n "${json_report}" && -f "${json_report}" ]]; then
        # Extract key metrics from Newman JSON report
        local total_tests=$(jq -r '.run.stats.assertions.total // 0' "${json_report}")
        local failed_tests=$(jq -r '.run.stats.assertions.failed // 0' "${json_report}")
        local total_requests=$(jq -r '.run.stats.requests.total // 0' "${json_report}")
        local failed_requests=$(jq -r '.run.stats.requests.failed // 0' "${json_report}")
        local avg_response_time=$(jq -r '.run.timings.responseAverage // 0' "${json_report}")
        
        # Create summary report
        cat > "${OUTPUT_DIR}/summary-${timestamp}.json" <<EOF
{
  "environment": "${ENVIRONMENT}",
  "timestamp": "$(date -Iseconds)",
  "status": "${test_result}",
  "metrics": {
    "total_tests": ${total_tests},
    "failed_tests": ${failed_tests},
    "success_rate": $(echo "scale=2; (${total_tests} - ${failed_tests}) / ${total_tests} * 100" | bc -l 2>/dev/null || echo "0"),
    "total_requests": ${total_requests},
    "failed_requests": ${failed_requests},
    "avg_response_time_ms": ${avg_response_time}
  },
  "reports": {
    "html": "$(basename "$(ls -t "${OUTPUT_DIR}"/smoke-test-${ENVIRONMENT}-*.html 2>/dev/null | head -1)")",
    "json": "$(basename "${json_report}")"
  }
}
EOF
        
        log "Test Summary:"
        log "  Environment: ${ENVIRONMENT}"
        log "  Total Tests: ${total_tests}"
        log "  Failed Tests: ${failed_tests}"
        log "  Success Rate: $(echo "scale=1; (${total_tests} - ${failed_tests}) / ${total_tests} * 100" | bc -l 2>/dev/null || echo "0")%"
        log "  Avg Response Time: ${avg_response_time}ms"
        
    else
        log "WARNING: No JSON report found for summary generation"
    fi
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    
    if [[ -n "${WEBHOOK_URL:-}" ]]; then
        local emoji="✅"
        local color="good"
        
        if [[ "${status}" == "failed" ]]; then
            emoji="❌"
            color="danger"
        fi
        
        local payload=$(cat <<EOF
{
  "attachments": [
    {
      "color": "${color}",
      "title": "${emoji} Smoke Test ${status^}",
      "text": "${message}",
      "fields": [
        {
          "title": "Environment",
          "value": "${ENVIRONMENT}",
          "short": true
        },
        {
          "title": "Timestamp",
          "value": "$(date -Iseconds)",
          "short": true
        }
      ]
    }
  ]
}
EOF
        )
        
        curl -X POST "${WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "${payload}" \
            --silent --fail || log "WARNING: Notification failed"
    fi
}

# Upload reports to S3
upload_reports() {
    if [[ -n "${S3_REPORTS_BUCKET:-}" ]] && command -v aws >/dev/null 2>&1; then
        log "Uploading reports to S3"
        
        aws s3 sync "${OUTPUT_DIR}" "s3://${S3_REPORTS_BUCKET}/smoke-tests/${ENVIRONMENT}/" \
            --exclude "*" \
            --include "*.html" \
            --include "*.json" \
            --include "summary-*.json"
        
        log "Reports uploaded to s3://${S3_REPORTS_BUCKET}/smoke-tests/${ENVIRONMENT}/"
    fi
}

# Main execution
main() {
    log "Starting smoke test execution"
    
    setup
    pre_test_validation
    
    local test_result="success"
    if ! run_smoke_tests; then
        test_result="failed"
    fi
    
    generate_summary "${test_result}"
    
    if [[ "${SEND_NOTIFICATIONS:-true}" == "true" ]]; then
        if [[ "${test_result}" == "success" ]]; then
            send_notification "success" "All smoke tests passed in ${ENVIRONMENT} environment"
        else
            send_notification "failed" "Some smoke tests failed in ${ENVIRONMENT} environment"
        fi
    fi
    
    upload_reports
    
    log "Smoke test execution completed with status: ${test_result}"
    
    if [[ "${test_result}" == "failed" ]]; then
        exit 1
    fi
}

# Usage information
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --environment ENV     Target environment (default: production)"
    echo "  --collection FILE     Postman collection file"
    echo "  --env-file FILE       Environment file"
    echo "  --output-dir DIR      Output directory for reports"
    echo "  --timeout MS          Request timeout in milliseconds"
    echo "  --delay MS            Delay between requests"
    echo "  --bail                Stop on first failure"
    echo "  --no-notifications    Disable notifications"
    echo "  --help                Show this help"
    echo ""
    echo "Environment variables:"
    echo "  WEBHOOK_URL           Slack webhook for notifications"
    echo "  S3_REPORTS_BUCKET     S3 bucket for report uploads"
    echo "  NEWMAN_GLOBALS        Global variables file"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            ENV_FILE="tests/smoke/environments/${ENVIRONMENT}.postman_environment.json"
            shift 2
            ;;
        --collection)
            COLLECTION_FILE="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --delay)
            DELAY_REQUEST="$2"
            shift 2
            ;;
        --bail)
            BAIL="true"
            shift
            ;;
        --no-notifications)
            SEND_NOTIFICATIONS="false"
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main function
main "$@"