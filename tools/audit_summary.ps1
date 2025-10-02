# PowerShell version of audit_summary.sh
param()

function Write-Pass($message) {
    Write-Host "PASS: $message" -ForegroundColor Green
}

function Write-Fail($message) {
    Write-Host "FAIL: $message" -ForegroundColor Red
    exit 1
}

# Check if ripgrep is available, otherwise use Select-String
$RG = $null
if (Get-Command rg -ErrorAction SilentlyContinue) {
    $RG = "rg"
} else {
    Write-Host "Warning: ripgrep (rg) not found, using PowerShell Select-String (slower)" -ForegroundColor Yellow
}

# Required files (adjusted for actual directory structure)
$need = @(
    "backend\docs\migration\users.md",
    "backend\tools\invite_existing_users.py", 
    "backend\docs\migration\etl.md",
    "backend\apps\core\supa_request.py",
    "supabase\patch_storage_policies.sql",
    "backend\tests\smoke_rls.sh",
    "backend\Makefile"
)

# Check required files exist
foreach ($f in $need) {    
    if (!(Test-Path $f)) {
        Write-Fail "missing $f"
    }
}
Write-Pass "required files exist"

# Check for legacy code in request path
if ($RG) {
    $legacyResult = & $RG -n "(sqlmodel|Session|get_session|boto3|s3|create_access_token|jwt\.encode)" backend\apps\api 2>$null
    if ($legacyResult) {
        Write-Fail "legacy code found in request path:`n$legacyResult"
    }
} else {
    $legacyFiles = Get-ChildItem -Path "backend\apps\api" -Recurse -Include "*.py" | 
        Select-String -Pattern "(sqlmodel|Session|get_session|boto3|s3|create_access_token|jwt\.encode)" 2>$null
    if ($legacyFiles) {
        Write-Fail "legacy code found in request path:`n$($legacyFiles -join "`n")"
    }
}
Write-Pass "no legacy in request path"

# Check for service role leaks in user paths
if ($RG) {
    $serviceLeaks = & $RG -n "service_client\(|Supa\.service\(\)" backend\apps 2>$null | 
        Where-Object { $_ -notmatch "entitlements\.py" -and $_ -notmatch "tools" -and $_ -notmatch "invite_existing_users\.py" }
    if ($serviceLeaks) {
        Write-Fail "service role leak in user paths:`n$serviceLeaks"
    }
} else {
    $serviceFiles = Get-ChildItem -Path "backend\apps" -Recurse -Include "*.py" |
        Select-String -Pattern "service_client\(|Supa\.service\(\)" 2>$null |
        Where-Object { $_.Filename -notmatch "entitlements\.py" -and $_.Path -notmatch "tools" -and $_.Filename -notmatch "invite_existing_users\.py" }
    if ($serviceFiles) {
        Write-Fail "service role leaks in user paths:`n$($serviceFiles -join "`n")"
    }
}
Write-Pass "no service role leaks in user paths"

# Check MODEL_PROVIDER (optional)
if ($RG) {
    $modelProvider = & $RG -n "MODEL_PROVIDER" backend 2>$null
    if (!$modelProvider) {
        Write-Pass "MODEL_PROVIDER not enforced (ok)"
    }
} else {
    $modelFiles = Get-ChildItem -Path "backend" -Recurse -Include "*.py" | 
        Select-String -Pattern "MODEL_PROVIDER" 2>$null
    if (!$modelFiles) {
        Write-Pass "MODEL_PROVIDER not enforced (ok)"
    }
}

Write-Host "OK" -ForegroundColor Green