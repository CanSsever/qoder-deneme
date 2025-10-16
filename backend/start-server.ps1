# Backend Startup Script for Windows
# Run this to start the backend server with proper configuration

Write-Host "=" -NoNewline; Write-Host ("=" * 49)
Write-Host "OneShot Backend Startup"
Write-Host "=" -NoNewline; Write-Host ("=" * 49)
Write-Host ""

# Check if in backend directory
$currentDir = Get-Location
if (-not (Test-Path "apps\api\main.py")) {
    Write-Host "ERROR: Please run this script from the backend directory" -ForegroundColor Red
    Write-Host "Current directory: $currentDir" -ForegroundColor Yellow
    Write-Host "Expected: [workspace]\backend" -ForegroundColor Yellow
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env file from .env.example" -ForegroundColor Green
    } else {
        Write-Host "ERROR: .env.example not found!" -ForegroundColor Red
        exit 1
    }
}

# Check Python installation
Write-Host "Checking Python installation..." -ForegroundColor Cyan
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python version: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Please install Python 3.8 or higher." -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Virtual environment not found. Creating one..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Check if requirements are installed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
$uvicornInstalled = pip list | Select-String "uvicorn"
if (-not $uvicornInstalled) {
    Write-Host "Dependencies not installed. Installing..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "Dependencies already installed" -ForegroundColor Green
}

# Get local IP address
$localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notmatch "^127\." -and 
    $_.IPAddress -notmatch "^169\.254\." -and
    $_.PrefixOrigin -eq "Dhcp" -or $_.PrefixOrigin -eq "Manual"
} | Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "=" -NoNewline; Write-Host ("=" * 49)
Write-Host "Server Configuration"
Write-Host "=" -NoNewline; Write-Host ("=" * 49)
Write-Host "Host: 0.0.0.0 (all interfaces)" -ForegroundColor Cyan
Write-Host "Port: 8000" -ForegroundColor Cyan
Write-Host "Local IP: $localIp" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Yellow
Write-Host "  - Localhost: http://localhost:8000" -ForegroundColor White
Write-Host "  - LAN IP: http://${localIp}:8000" -ForegroundColor White
Write-Host "  - Android Emulator: http://10.0.2.2:8000" -ForegroundColor White
Write-Host "  - iOS Simulator: http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "Health Check: http://localhost:8000/healthz" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "=" -NoNewline; Write-Host ("=" * 49)
Write-Host ""

# Check if port 8000 is already in use
$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "WARNING: Port 8000 is already in use!" -ForegroundColor Red
    Write-Host "Process using port 8000:" -ForegroundColor Yellow
    Get-NetTCPConnection -LocalPort 8000 -State Listen | 
        ForEach-Object { Get-Process -Id $_.OwningProcess } | 
        Format-Table ProcessName, Id, Path -AutoSize
    
    $continue = Read-Host "Do you want to continue anyway? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Startup cancelled" -ForegroundColor Yellow
        exit 0
    }
}

# Start the server
Write-Host "Starting server..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
