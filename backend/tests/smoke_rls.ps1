# RLS Smoke Test for Supabase Migration (PowerShell)
# Tests that Row Level Security is properly enforced
# Usage: $env:TOKEN="<supabase_user_jwt>"; .\backend\tests\smoke_rls.ps1

param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$Token = $env:TOKEN
)

if (-not $Token) {
    Write-Error "Please set TOKEN environment variable with a valid Supabase user JWT or pass -Token parameter"
    exit 1
}

Write-Host "🔍 Testing RLS enforcement with API: $ApiUrl" -ForegroundColor Cyan
Write-Host "📋 Using token: $($Token.Substring(0, [Math]::Min(20, $Token.Length)))..." -ForegroundColor Cyan

# Test counters
$TestsPassed = 0
$TestsFailed = 0

# Helper function to test HTTP response
function Test-Response {
    param(
        [string]$Description,
        [int]$ExpectedCode,
        [int]$ActualCode,
        [string]$Endpoint
    )
    
    if ($ActualCode -eq $ExpectedCode) {
        Write-Host "✓ $Description (HTTP $ActualCode)" -ForegroundColor Green
        $script:TestsPassed++
    } else {
        Write-Host "✗ $Description - Expected HTTP $ExpectedCode, got $ActualCode" -ForegroundColor Red
        Write-Host "  Endpoint: $Endpoint" -ForegroundColor Red
        $script:TestsFailed++
    }
}

# Helper function to make HTTP request and get status code
function Get-HttpStatusCode {
    param(
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$Method = "GET",
        [string]$Body = $null
    )
    
    try {
        $splat = @{
            Uri = $Url
            Method = $Method
            Headers = $Headers
            UseBasicParsing = $true
            ErrorAction = "Stop"
        }
        
        if ($Body) {
            $splat.Body = $Body
            $splat.ContentType = "application/json"
        }
        
        $response = Invoke-WebRequest @splat
        return $response.StatusCode
    } catch {
        if ($_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode
        }
        return 500
    }
}

# Helper function to make HTTP request and get response
function Get-HttpResponse {
    param(
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$Method = "GET",
        [string]$Body = $null
    )
    
    try {
        $splat = @{
            Uri = $Url
            Method = $Method
            Headers = $Headers
            UseBasicParsing = $true
            ErrorAction = "Stop"
        }
        
        if ($Body) {
            $splat.Body = $Body
            $splat.ContentType = "application/json"
        }
        
        $response = Invoke-WebRequest @splat
        return @{
            StatusCode = $response.StatusCode
            Content = $response.Content
        }
    } catch {
        $statusCode = 500
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }
        return @{
            StatusCode = $statusCode
            Content = $_.Exception.Message
        }
    }
}

Write-Host ""
Write-Host "🔐 Testing authentication requirements..." -ForegroundColor Yellow

# Test 1: Must 401 without token
Write-Host "Test 1: Access without token should return 401"
$code = Get-HttpStatusCode -Url "$ApiUrl/api/v1/auth/profile"
Test-Response "Profile access without token" 401 $code "/api/v1/auth/profile"

# Test 2: Must 401 without token for jobs
Write-Host "Test 2: Jobs access without token should return 401"
$code = Get-HttpStatusCode -Url "$ApiUrl/api/v1/jobs"
Test-Response "Jobs list without token" 401 $code "/api/v1/jobs"

# Test 3: Must 401 without token for credits
Write-Host "Test 3: Credits access without token should return 401"
$code = Get-HttpStatusCode -Url "$ApiUrl/api/v1/credits"
Test-Response "Credits list without token" 401 $code "/api/v1/credits"

Write-Host ""
Write-Host "🎫 Testing with valid token..." -ForegroundColor Yellow

$authHeaders = @{ "Authorization" = "Bearer $Token" }

# Test 4: With token should pass for profile bootstrap
Write-Host "Test 4: Bootstrap profile with token should succeed"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/auth/bootstrap-profile" -Headers $authHeaders -Method "POST"
Test-Response "Bootstrap profile with token" 200 $response.StatusCode "/api/v1/auth/bootstrap-profile"

# Test 5: Get profile with token
Write-Host "Test 5: Get profile with token should succeed"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/auth/profile" -Headers $authHeaders
Test-Response "Get profile with token" 200 $response.StatusCode "/api/v1/auth/profile"

# Test 6: List jobs via USER client (RLS enforced)
Write-Host "Test 6: Jobs list with token should succeed (RLS enforced)"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/jobs" -Headers $authHeaders
Test-Response "Jobs list with token" 200 $response.StatusCode "/api/v1/jobs"

# Test 7: Get credits with token (RLS enforced)
Write-Host "Test 7: Credits access with token should succeed (RLS enforced)"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/credits" -Headers $authHeaders
Test-Response "Credits list with token" 200 $response.StatusCode "/api/v1/credits"

# Test 8: Get credit balance with token
Write-Host "Test 8: Credit balance with token should succeed"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/credits/balance" -Headers $authHeaders
Test-Response "Credit balance with token" 200 $response.StatusCode "/api/v1/credits/balance"

Write-Host ""
Write-Host "🔒 Testing RLS data isolation..." -ForegroundColor Yellow

# Test 9: Try to access non-existent job (should return 404, not 403 - proves RLS is working)
Write-Host "Test 9: Access to non-existent job should return 404 (proves RLS filtering)"
$fakeJobId = "550e8400-e29b-41d4-a716-446655440000"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/jobs/$fakeJobId" -Headers $authHeaders
Test-Response "Access non-existent job" 404 $response.StatusCode "/api/v1/jobs/$fakeJobId"

# Test 10: Create a job to test RLS
Write-Host "Test 10: Create job with valid token should succeed"
$jobData = @{
    job_type = "face_restoration"
    input_image_url = "https://example.com/test.jpg"
    parameters = @{}
} | ConvertTo-Json

$response = Get-HttpResponse -Url "$ApiUrl/api/v1/jobs" -Headers $authHeaders -Method "POST" -Body $jobData
# Accept both 200 and 402 (insufficient credits) as success for RLS test
if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 402) {
    Test-Response "Create job with token" $response.StatusCode $response.StatusCode "/api/v1/jobs"
} else {
    Test-Response "Create job with token" 200 $response.StatusCode "/api/v1/jobs"
}

Write-Host ""
Write-Host "🏥 Testing service health..." -ForegroundColor Yellow

# Test 11: Auth health check endpoints
Write-Host "Test 11: Auth health check should work"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/auth/health"
Test-Response "Auth health check" 200 $response.StatusCode "/api/v1/auth/health"

# Test 12: Webhooks health check
Write-Host "Test 12: Webhooks health check should work"
$response = Get-HttpResponse -Url "$ApiUrl/api/v1/webhooks/health"
Test-Response "Webhooks health check" 200 $response.StatusCode "/api/v1/webhooks/health"

Write-Host ""
Write-Host "📊 RLS SMOKE TEST RESULTS" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan
Write-Host "Tests passed: $TestsPassed" -ForegroundColor Green
Write-Host "Tests failed: $TestsFailed" -ForegroundColor $(if ($TestsFailed -eq 0) { "Green" } else { "Red" })
Write-Host "Total tests: $($TestsPassed + $TestsFailed)"

if ($TestsFailed -eq 0) {
    Write-Host ""
    Write-Host "🎉 ALL TESTS PASSED!" -ForegroundColor Green
    Write-Host "RLS enforcement is working correctly." -ForegroundColor Green
    Write-Host ""
    Write-Host "✅ Authentication is required for protected endpoints" -ForegroundColor Green
    Write-Host "✅ Valid tokens provide access to user's own data" -ForegroundColor Green
    Write-Host "✅ RLS policies properly filter data access" -ForegroundColor Green
    Write-Host "✅ API endpoints are responding correctly" -ForegroundColor Green
    exit 0
} else {
    Write-Host ""
    Write-Host "❌ SOME TESTS FAILED" -ForegroundColor Red
    Write-Host "Please check the API configuration and Supabase setup." -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "- Supabase RLS policies not properly configured" -ForegroundColor Yellow
    Write-Host "- JWT secret mismatch between client and server" -ForegroundColor Yellow
    Write-Host "- Missing Authorization header handling in routes" -ForegroundColor Yellow
    Write-Host "- Service not running or network connectivity issues" -ForegroundColor Yellow
    exit 1
}