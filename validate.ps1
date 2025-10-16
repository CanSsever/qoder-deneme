# OneShot - Pre-Launch Validation Script
# Run this to ensure everything is configured correctly before starting

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host "OneShot - Pre-Launch Validation"
Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host ""

$allChecks = @()

# Check 1: Backend directory exists
Write-Host "[1/8] Checking backend directory..." -ForegroundColor Cyan
if (Test-Path "backend\apps\api\main.py") {
    Write-Host "  OK Backend directory found" -ForegroundColor Green
    $allChecks += $true
} else {
    Write-Host "  ERROR Backend directory not found" -ForegroundColor Red
    $allChecks += $false
}

# Check 2: Frontend directory exists
Write-Host "[2/8] Checking frontend directory..." -ForegroundColor Cyan
if (Test-Path "frontend\expo-app\package.json") {
    Write-Host "  OK Frontend directory found" -ForegroundColor Green
    $allChecks += $true
} else {
    Write-Host "  ERROR Frontend directory not found" -ForegroundColor Red
    $allChecks += $false
}

# Check 3: Python installed
Write-Host "[3/8] Checking Python installation..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  OK Python installed: $pythonVersion" -ForegroundColor Green
    $allChecks += $true
} catch {
    Write-Host "  ERROR Python not found" -ForegroundColor Red
    $allChecks += $false
}

# Check 4: Node.js installed
Write-Host "[4/8] Checking Node.js installation..." -ForegroundColor Cyan
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  OK Node.js installed: $nodeVersion" -ForegroundColor Green
    $allChecks += $true
} catch {
    Write-Host "  ERROR Node.js not found" -ForegroundColor Red
    $allChecks += $false
}

# Check 5: Backend .env exists
Write-Host "[5/8] Checking backend .env file..." -ForegroundColor Cyan
if (Test-Path "backend\.env") {
    Write-Host "  OK Backend .env found" -ForegroundColor Green
    $allChecks += $true
} else {
    Write-Host "  ERROR Backend .env not found" -ForegroundColor Red
    Write-Host "    Copy backend\.env.example to backend\.env" -ForegroundColor Yellow
    $allChecks += $false
}

# Check 6: Frontend .env exists
Write-Host "[6/8] Checking frontend .env file..." -ForegroundColor Cyan
if (Test-Path "frontend\expo-app\.env") {
    Write-Host "  OK Frontend .env found" -ForegroundColor Green
    $allChecks += $true
} else {
    Write-Host "  WARNING Frontend .env not found (using defaults)" -ForegroundColor Yellow
    $allChecks += $true  # Not critical, has defaults
}

# Check 7: Port 8000 availability
Write-Host "[7/8] Checking port 8000 availability..." -ForegroundColor Cyan
$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "  WARNING Port 8000 is already in use" -ForegroundColor Yellow
    Write-Host "    Backend may already be running or another service is using this port" -ForegroundColor Yellow
    $allChecks += $true  # Not a failure, might be intentional
} else {
    Write-Host "  OK Port 8000 is available" -ForegroundColor Green
    $allChecks += $true
}

# Check 8: Network connectivity
Write-Host "[8/8] Checking network configuration..." -ForegroundColor Cyan
$localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notmatch "^127\." -and 
    $_.IPAddress -notmatch "^169\.254\." -and
    ($_.PrefixOrigin -eq "Dhcp" -or $_.PrefixOrigin -eq "Manual")
} | Select-Object -First 1).IPAddress

if ($localIp) {
    Write-Host "  OK Local IP detected: $localIp" -ForegroundColor Green
    $allChecks += $true
} else {
    Write-Host "  WARNING Could not detect local IP" -ForegroundColor Yellow
    $allChecks += $true  # Not critical for localhost testing
}

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("=" * 59)

$passedChecks = ($allChecks | Where-Object { $_ -eq $true }).Count
$totalChecks = $allChecks.Count

if ($passedChecks -eq $totalChecks) {
    Write-Host "SUCCESS: All checks passed ($passedChecks/$totalChecks)" -ForegroundColor Green
    Write-Host "=" -NoNewline; Write-Host ("=" * 59)
    Write-Host ""
    Write-Host "Ready to start!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Open a new terminal and start backend:" -ForegroundColor White
    Write-Host "     cd backend" -ForegroundColor Gray
    Write-Host "     .\start-server.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. In another terminal, check API connectivity:" -ForegroundColor White
    Write-Host "     cd frontend\expo-app" -ForegroundColor Gray
    Write-Host "     npm run check:api" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  3. Start the Expo app:" -ForegroundColor White
    Write-Host "     npm start" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Documentation:" -ForegroundColor Cyan
    Write-Host "  - Quick Start: QUICK_START.md" -ForegroundColor White
    Write-Host "  - Full Guide: NETWORK_TIMEOUT_FIX.md" -ForegroundColor White
    Write-Host "  - Summary: FIX_SUMMARY.md" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "WARNING: Some checks failed ($passedChecks/$totalChecks passed)" -ForegroundColor Yellow
    Write-Host "=" -NoNewline; Write-Host ("=" * 59)
    Write-Host ""
    Write-Host "Please resolve the issues above before continuing." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "For help, see:" -ForegroundColor Cyan
    Write-Host "  - QUICK_START.md" -ForegroundColor White
    Write-Host "  - NETWORK_TIMEOUT_FIX.md" -ForegroundColor White
    Write-Host ""
}

# Display network configuration
if ($localIp) {
    Write-Host "Network Configuration:" -ForegroundColor Cyan
    Write-Host "  Localhost: http://localhost:8000" -ForegroundColor White
    Write-Host "  LAN IP: http://${localIp}:8000" -ForegroundColor White
    Write-Host "  Android Emulator: http://10.0.2.2:8000" -ForegroundColor White
    Write-Host "  iOS Simulator: http://localhost:8000" -ForegroundColor White
    Write-Host ""
}

Write-Host "=" -NoNewline; Write-Host ("=" * 59)
Write-Host ""
