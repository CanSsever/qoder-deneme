# OneShot Face Swapper - Smoke Test Script (PowerShell)
# Usage: .\scripts\smoke-test.ps1 -BaseUrl "https://your-api.com" [-Timeout 30]

param(
    [Parameter(Mandatory = $false)]
    [string]$BaseUrl = "http://localhost:8000",
    
    [Parameter(Mandatory = $false)]
    [int]$Timeout = 30
)

# Test counters
$script:TestsTotal = 0
$script:TestsPassed = 0
$script:TestsFailed = 0

# Colors
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Cyan"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message" -ForegroundColor $Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor $Green
    $script:TestsPassed++
}

function Write-Failure {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor $Red
    $script:TestsFailed++
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor $Yellow
}

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$ExpectedStatus = 200,
        [string]$Method = "GET",
        [string]$Data = $null,
        [hashtable]$Headers = @{}
    )
    
    $script:TestsTotal++
    
    Write-Log "Testing $Name..."
    
    try {
        $requestParams = @{
            Uri = $Url
            Method = $Method
            TimeoutSec = $Timeout
            UseBasicParsing = $true
            ErrorAction = "SilentlyContinue"
        }
        
        if ($Headers.Count -gt 0) {
            $requestParams.Headers = $Headers
        }
        
        if ($Data) {
            $requestParams.Body = $Data
            $requestParams.ContentType = "application/json"
        }
        
        $response = Invoke-WebRequest @requestParams
        $statusCode = $response.StatusCode
        
        if ($statusCode -eq $ExpectedStatus) {
            Write-Success "$Name (HTTP $statusCode)"
            if ($response.Content -and $response.Content.Length -lt 200) {
                Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
            }
        } else {
            Write-Failure "$Name (Expected HTTP $ExpectedStatus, got $statusCode)"
        }
    }
    catch {
        $errorStatus = if ($_.Exception.Response) { 
            $_.Exception.Response.StatusCode.value__ 
        } else { 
            "Connection Error" 
        }
        
        if ($errorStatus -eq $ExpectedStatus) {
            Write-Success "$Name (HTTP $errorStatus)"
        } else {
            Write-Failure "$Name (Expected HTTP $ExpectedStatus, got $errorStatus)"
            if ($_.Exception.Message) {
                Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
            }
        }
    }
}

# Banner
Write-Host "==================================================" -ForegroundColor White
Write-Host "   OneShot Face Swapper - Smoke Tests (PowerShell)" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor White
Write-Host "Base URL: $BaseUrl"
Write-Host "Timeout: ${Timeout}s"
Write-Host "Started: $(Get-Date)"
Write-Host "==================================================" -ForegroundColor White

# Core Health Checks
Write-Log "Running core health checks..."
Test-Endpoint -Name "Health Check" -Url "$BaseUrl/healthz"
Test-Endpoint -Name "Readiness Check" -Url "$BaseUrl/readyz"
Test-Endpoint -Name "API Documentation" -Url "$BaseUrl/docs"
Test-Endpoint -Name "OpenAPI Spec" -Url "$BaseUrl/openapi.json"

# Metrics and Monitoring
Write-Log "Testing monitoring endpoints..."
Test-Endpoint -Name "Metrics" -Url "$BaseUrl/metrics"

# Authentication Endpoints
Write-Log "Testing authentication endpoints..."
Test-Endpoint -Name "Auth Login Endpoint" -Url "$BaseUrl/auth/login" -ExpectedStatus 422 -Method "POST" -Data '{"email":"test@example.com","password":"wrongpassword"}'

# API Endpoints (without authentication)
Write-Log "Testing API endpoints (unauthenticated)..."
Test-Endpoint -Name "Get Jobs (Unauthorized)" -Url "$BaseUrl/jobs" -ExpectedStatus 401
Test-Endpoint -Name "Upload Presign (Unauthorized)" -Url "$BaseUrl/uploads/presign" -ExpectedStatus 401 -Method "POST" -Data '{"filename":"test.jpg","content_type":"image/jpeg","file_size":1024}'

# Billing Endpoints
Write-Log "Testing billing endpoints..."
Test-Endpoint -Name "Billing Webhook" -Url "$BaseUrl/billing/webhook" -ExpectedStatus 422 -Method "POST" -Data '{}'

# Error Handling
Write-Log "Testing error handling..."
Test-Endpoint -Name "Not Found" -Url "$BaseUrl/nonexistent" -ExpectedStatus 404
Test-Endpoint -Name "Method Not Allowed" -Url "$BaseUrl/auth/login" -ExpectedStatus 405 -Method "PUT"

# Performance Test
Write-Log "Testing performance..."
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
Test-Endpoint -Name "Response Time Test" -Url "$BaseUrl/healthz"
$stopwatch.Stop()
$responseTime = $stopwatch.ElapsedMilliseconds

if ($responseTime -lt 1000) {
    Write-Success "Response time: ${responseTime}ms (< 1000ms)"
} else {
    Write-Warning "Response time: ${responseTime}ms (>= 1000ms)"
}

# CORS Headers Test
Write-Log "Testing CORS headers..."
try {
    $corsHeaders = @{
        "Origin" = "https://example.com"
        "Access-Control-Request-Method" = "POST"
        "Access-Control-Request-Headers" = "Content-Type"
    }
    
    $corsResponse = Invoke-WebRequest -Uri "$BaseUrl/auth/login" -Method "OPTIONS" -Headers $corsHeaders -UseBasicParsing -ErrorAction SilentlyContinue
    
    $script:TestsTotal++
    if ($corsResponse.Headers["Access-Control-Allow-Origin"]) {
        Write-Success "CORS headers present"
        $script:TestsPassed++
    } else {
        Write-Failure "CORS headers missing"
        $script:TestsFailed++
    }
}
catch {
    $script:TestsTotal++
    Write-Warning "Could not test CORS headers"
    $script:TestsFailed++
}

# Security Headers Test
Write-Log "Testing security headers..."
try {
    $securityResponse = Invoke-WebRequest -Uri "$BaseUrl/docs" -Method "HEAD" -UseBasicParsing -ErrorAction SilentlyContinue
    
    $securityChecks = @(
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection"
    )
    
    foreach ($header in $securityChecks) {
        $script:TestsTotal++
        if ($securityResponse.Headers[$header]) {
            Write-Success "Security header: $header"
            $script:TestsPassed++
        } else {
            Write-Warning "Missing security header: $header"
            $script:TestsFailed++
        }
    }
}
catch {
    Write-Warning "Could not test security headers"
}

# SSL/TLS Test (if HTTPS)
if ($BaseUrl.StartsWith("https://")) {
    Write-Log "Testing SSL/TLS configuration..."
    $script:TestsTotal++
    try {
        $sslResponse = Invoke-WebRequest -Uri "$BaseUrl/healthz" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        Write-Success "SSL/TLS connection successful"
        $script:TestsPassed++
    }
    catch {
        Write-Failure "SSL/TLS connection failed"
        $script:TestsFailed++
    }
}

# Database Connectivity Test (indirect)
Write-Log "Testing database connectivity (indirect)..."
Test-Endpoint -Name "Database Health" -Url "$BaseUrl/readyz"

# Results Summary
Write-Host "`n==================================================" -ForegroundColor White
Write-Host "   Smoke Test Results" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor White
Write-Host "Total Tests: $script:TestsTotal"
Write-Host "Passed: " -NoNewline
Write-Host "$script:TestsPassed" -ForegroundColor $Green
Write-Host "Failed: " -NoNewline
Write-Host "$script:TestsFailed" -ForegroundColor $Red

if ($script:TestsFailed -eq 0) {
    Write-Host "`n🎉 All smoke tests passed!" -ForegroundColor $Green
    Write-Host "Deployment appears to be healthy."
    exit 0
} else {
    Write-Host "`n❌ Some smoke tests failed!" -ForegroundColor $Red
    Write-Host "Please investigate the failures before proceeding."
    exit 1
}