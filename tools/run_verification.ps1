# PowerShell version of verification targets
# Usage: .\tools\run_verification.ps1 -Target audit|scan-service-role|test-rls

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("audit", "scan-service-role", "test-rls")]
    [string]$Target,
    
    [string]$TokenA = $env:TOKEN_A,
    [string]$TokenB = $env:TOKEN_B,
    [string]$ApiUrl = $env:API
)

function Write-Header($message) {
    Write-Host "`n=== $message ===" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "✅ $message" -ForegroundColor Green
}

function Write-Error($message) {
    Write-Host "❌ $message" -ForegroundColor Red
}

switch ($Target) {
    "audit" {
        Write-Header "Running Supabase migration audit"
        & powershell -ExecutionPolicy Bypass -File tools\audit_summary.ps1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Audit completed successfully"
        } else {
            Write-Error "Audit failed - see output above for details"
            exit 1
        }
    }
    
    "scan-service-role" {
        Write-Header "Scanning for service role leaks in user paths"
        & powershell -ExecutionPolicy Bypass -File tools\scan_service_role_leaks.ps1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "No service role leaks found"
        } else {
            Write-Error "Service role leaks detected - see output above"
            exit 1
        }
    }
    
    "test-rls" {
        Write-Header "Testing RLS isolation between users"
        if (-not $TokenA -or -not $TokenB) {
            Write-Error "TOKEN_A and TOKEN_B environment variables required"
            Write-Host "Set TOKEN_A=<jwt_user_a> TOKEN_B=<jwt_user_b>" -ForegroundColor Yellow
            exit 1
        }
        
        $env:TOKEN_A = $TokenA
        $env:TOKEN_B = $TokenB
        $env:API = if ($ApiUrl) { $ApiUrl } else { "http://localhost:8000" }
        
        Write-Host "Using API: $($env:API)" -ForegroundColor Yellow
        Write-Host "Note: RLS test requires bash - checking for Git Bash or WSL..." -ForegroundColor Yellow
        
        # Try different bash locations
        $bashPaths = @(
            "C:\Program Files\Git\bin\bash.exe",
            "C:\Git\bin\bash.exe",
            "bash"
        )
        
        $bashFound = $false
        foreach ($bashPath in $bashPaths) {
            try {
                if (Test-Path $bashPath -ErrorAction SilentlyContinue) {
                    Write-Host "Found bash at: $bashPath" -ForegroundColor Green
                    & $bashPath backend/tests/smoke_rls.sh
                    $bashFound = $true
                    break
                } elseif ($bashPath -eq "bash") {
                    # Try to run bash directly (might be in PATH)
                    & bash backend/tests/smoke_rls.sh 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        $bashFound = $true
                        break
                    }
                }
            } catch {
                continue
            }
        }
        
        if (-not $bashFound) {
            Write-Error "Bash not found. Please install Git for Windows or WSL to run RLS tests"
            Write-Host "Or manually test RLS using curl commands:" -ForegroundColor Yellow
            Write-Host "1. curl -H 'Authorization: Bearer <TOKEN_A>' $($env:API)/api/bootstrap-profile" -ForegroundColor Gray
            Write-Host "2. curl -X POST -H 'Authorization: Bearer <TOKEN_A>' -H 'Content-Type: application/json' $($env:API)/api/jobs -d '{...}'" -ForegroundColor Gray
            Write-Host "3. curl -H 'Authorization: Bearer <TOKEN_B>' $($env:API)/api/jobs (should not see TOKEN_A's job)" -ForegroundColor Gray
            exit 1
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "RLS isolation test passed"
        } else {
            Write-Error "RLS isolation test failed"
            exit 1
        }
    }
}