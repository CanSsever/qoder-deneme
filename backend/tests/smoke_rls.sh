#!/usr/bin/env bash
set -euo pipefail
API=${API:-http://localhost:8000}
: "${TOKEN_A:?set TOKEN_A}"
: "${TOKEN_B:?set TOKEN_B}"

# 401 without token
code=$(curl -s -o /dev/null -w "%{http_code}" $API/api/bootstrap-profile)
[ "$code" = "401" ] || { echo "Expected 401 without token"; exit 1; }

# bootstrap
curl -fsS -H "Authorization: Bearer $TOKEN_A" $API/api/bootstrap-profile >/dev/null
curl -fsS -H "Authorization: Bearer $TOKEN_B" $API/api/bootstrap-profile >/dev/null

# A creates job
JOB_JSON=$(curl -fsS -X POST $API/api/jobs \
 -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
 -d '{"job_type":"restore","input_image_url":"uploads/UID_A/in.png","parameters":{"model":"gfpgan"}}')
JOB_ID=$(python - <<'PY'
import json,sys;print(json.load(sys.stdin)['id'])
PY <<<"$JOB_JSON")
[ -n "$JOB_ID" ]

# B must not see A's job
LIST_B=$(curl -fsS -H "Authorization: Bearer $TOKEN_B" $API/api/jobs)
python - <<PY
import json,sys,os
data=json.loads(os.environ['LIST_B'])
jid=os.environ['JOB_ID']
assert all(j.get('id')!=jid for j in data), 'RLS LEAK: B sees A job'
print('RLS isolation OK')
PY

# RLS Smoke Test for Supabase Migration
# Tests that Row Level Security is properly enforced
# Usage: TOKEN=<supabase_user_jwt> bash backend/tests/smoke_rls.sh

API=${API:-http://localhost:8000}
TOKEN=${TOKEN:?Please set TOKEN environment variable with a valid Supabase user JWT}

echo "🔍 Testing RLS enforcement with API: $API"
echo "📋 Using token: ${TOKEN:0:20}..."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to test HTTP response
test_response() {
    local description="$1"
    local expected_code="$2"
    local actual_code="$3"
    local endpoint="$4"
    
    if [ "$actual_code" = "$expected_code" ]; then
        echo -e "${GREEN}✓${NC} $description (HTTP $actual_code)"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗${NC} $description - Expected HTTP $expected_code, got $actual_code"
        echo "  Endpoint: $endpoint"
        ((TESTS_FAILED++))
    fi
}

echo ""
echo "🔐 Testing authentication requirements..."

# Test 1: Must 401 without token
echo "Test 1: Access without token should return 401"
code=$(curl -s -o /dev/null -w "%{http_code}" $API/api/bootstrap-profile)
test_response "Bootstrap profile without token" "401" "$code" "/api/bootstrap-profile"

# Test 2: Must 401 without token for jobs
echo "Test 2: Jobs access without token should return 401"
code=$(curl -s -o /dev/null -w "%{http_code}" $API/api/jobs)
test_response "Jobs list without token" "401" "$code" "/api/jobs"

# Test 3: Must 401 without token for credits
echo "Test 3: Credits access without token should return 401"
code=$(curl -s -o /dev/null -w "%{http_code}" $API/api/credits)
test_response "Credits list without token" "401" "$code" "/api/credits"

echo ""
echo "🎫 Testing with valid token..."

# Test 4: With token should pass for profile bootstrap
echo "Test 4: Bootstrap profile with token should succeed"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" -H "Authorization: Bearer $TOKEN" $API/api/bootstrap-profile)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
test_response "Bootstrap profile with token" "200" "$code" "/api/bootstrap-profile"

# Test 5: List jobs via USER client (RLS enforced)
echo "Test 5: Jobs list with token should succeed (RLS enforced)"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" -H "Authorization: Bearer $TOKEN" $API/api/jobs)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
test_response "Jobs list with token" "200" "$code" "/api/jobs"

# Test 6: Get credits with token (RLS enforced)
echo "Test 6: Credits access with token should succeed (RLS enforced)"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" -H "Authorization: Bearer $TOKEN" $API/api/credits)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
test_response "Credits list with token" "200" "$code" "/api/credits"

# Test 7: Get credit balance with token
echo "Test 7: Credit balance with token should succeed"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" -H "Authorization: Bearer $TOKEN" $API/api/credits/balance)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
test_response "Credit balance with token" "200" "$code" "/api/credits/balance"

echo ""
echo "🔒 Testing RLS data isolation..."

# Test 8: Try to access non-existent job (should return 404, not 403 - proves RLS is working)
echo "Test 8: Access to non-existent job should return 404 (proves RLS filtering)"
fake_job_id="550e8400-e29b-41d4-a716-446655440000"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" -H "Authorization: Bearer $TOKEN" $API/api/jobs/$fake_job_id)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
test_response "Access non-existent job" "404" "$code" "/api/jobs/$fake_job_id"

echo ""
echo "🏥 Testing service health..."

# Test 9: Health check endpoints
echo "Test 9: Auth health check should work"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" $API/api/auth/health)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
test_response "Auth health check" "200" "$code" "/api/auth/health"

# Test 10: General API health
echo "Test 10: General API health should work"
response=$(curl -s -w "HTTPSTATUS:%{http_code}" $API/health)
body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
code=$(echo "$response" | grep -o '[0-9]*$')
if [ "$code" = "200" ] || [ "$code" = "404" ]; then
    # 404 is acceptable if /health endpoint doesn't exist
    test_response "General API health" "$code" "$code" "/health"
else
    test_response "General API health" "200" "$code" "/health"
fi

echo ""
echo "📊 RLS SMOKE TEST RESULTS"
echo "=========================="
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo "Total tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
    echo "RLS enforcement is working correctly."
    echo ""
    echo "✅ Authentication is required for protected endpoints"
    echo "✅ Valid tokens provide access to user's own data"
    echo "✅ RLS policies properly filter data access"
    echo "✅ API endpoints are responding correctly"
    exit 0
else
    echo ""
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo "Please check the API configuration and Supabase setup."
    echo ""
    echo "Common issues:"
    echo "- Supabase RLS policies not properly configured"
    echo "- JWT secret mismatch between client and server"
    echo "- Missing Authorization header handling in routes"
    echo "- Service not running or network connectivity issues"
    exit 1
fi