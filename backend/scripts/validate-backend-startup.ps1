# Backend Startup Validation Service (PowerShell)
# Ensures backend is correctly configured for mobile device access

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"

# Colors
function Write-Success { param($Message) Write-Host "✓ $Message" -ForegroundColor Green }
function Write-Warning { param($Message) Write-Host "⚠ $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "✗ $Message" -ForegroundColor Red }
function Write-Info { param($Message) Write-Host "ℹ $Message" -ForegroundColor Cyan }
function Write-Header { param($Message) Write-Host "`n$Message" -ForegroundColor White -BackgroundColor DarkBlue }

$Issues = @()
$Warnings = @()

# Print header
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "OneShot Backend Startup Validator" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

# Check port availability
Write-Host "Checking port $Port availability..."
$PortInUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

if ($PortInUse) {
    Write-Warning "Port $Port is already in use"
    $Warnings += "Port $Port is in use. Make sure it's your backend server."
} else {
    Write-Success "Port $Port is available"
}

# Check health endpoint
Write-Host "`nValidating backend accessibility..."

try {
    $LocalhostResponse = Invoke-WebRequest -Uri "http://localhost:$Port/healthz" -TimeoutSec 5 -UseBasicParsing
    if ($LocalhostResponse.StatusCode -eq 200) {
        Write-Success "Backend accessible on localhost"
    }
} catch {
    Write-Error "Backend not accessible on localhost"
    $Issues += "Backend not responding on localhost"
}

# Get network interfaces
Write-Host "`nTesting network interface access..."

$NetworkInterfaces = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -eq "Dhcp" -or $_.PrefixOrigin -eq "Manual"
}

$AccessibleIPs = @()

foreach ($Interface in $NetworkInterfaces) {
    $IP = $Interface.IPAddress
    $InterfaceAlias = $Interface.InterfaceAlias
    
    try {
        $Response = Invoke-WebRequest -Uri "http://${IP}:$Port/healthz" -TimeoutSec 3 -UseBasicParsing
        if ($Response.StatusCode -eq 200) {
            Write-Success "Accessible on $InterfaceAlias ($IP)"
            $AccessibleIPs += $IP
        }
    } catch {
        Write-Warning "Not accessible on $InterfaceAlias ($IP)"
    }
}

if ($AccessibleIPs.Count -eq 0) {
    Write-Error "Backend not accessible from any network interface"
    $Issues += "Backend is not accessible from network. Check binding (use --host 0.0.0.0)"
}

# Check Windows Firewall
Write-Host "`nChecking firewall configuration..."

try {
    $FirewallRules = Get-NetFirewallRule | Where-Object {
        $_.Enabled -eq $true -and $_.Direction -eq "Inbound"
    }
    
    $PortRules = $FirewallRules | Get-NetFirewallPortFilter | Where-Object {
        $_.LocalPort -eq $Port
    }
    
    if ($PortRules) {
        Write-Success "Firewall rule exists for port $Port"
    } else {
        Write-Warning "No firewall rule found for port $Port"
        $Warnings += "Consider adding firewall rule: New-NetFirewallRule -DisplayName 'OneShot Backend' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow"
    }
} catch {
    Write-Warning "Cannot check Windows Firewall: $_"
}

# Generate access URLs
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Network Configuration" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`nLocalhost:        http://localhost:$Port"

if ($NetworkInterfaces) {
    Write-Host "`nNetwork Interfaces:"
    foreach ($Interface in $NetworkInterfaces) {
        $Alias = $Interface.InterfaceAlias.PadRight(15)
        $IP = $Interface.IPAddress
        Write-Host "  $Alias http://${IP}:$Port"
    }
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Mobile Access URLs" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`nAndroid Emulator: http://10.0.2.2:$Port"
Write-Host "iOS Simulator:    http://localhost:$Port"

if ($AccessibleIPs.Count -gt 0) {
    $PrimaryIP = $AccessibleIPs[0]
    Write-Host "Physical Devices: http://${PrimaryIP}:$Port"
} else {
    Write-Host "Physical Devices: http://192.168.1.x:$Port (update with your LAN IP)"
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Quick Test Commands" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`nInvoke-WebRequest -Uri http://localhost:$Port/healthz"

if ($AccessibleIPs.Count -gt 0) {
    $PrimaryIP = $AccessibleIPs[0]
    Write-Host "Invoke-WebRequest -Uri http://${PrimaryIP}:$Port/healthz"
}

Write-Host "`nAPI Documentation: http://localhost:$Port/docs"

# Print summary
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Validation Summary" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

if ($Issues.Count -eq 0 -and $Warnings.Count -eq 0) {
    Write-Success "All checks passed!"
    Write-Success "Backend is ready for mobile development."
} else {
    if ($Issues.Count -gt 0) {
        Write-Host "Issues Found:" -ForegroundColor Red
        foreach ($Issue in $Issues) {
            Write-Error "  $Issue"
        }
        Write-Host ""
    }
    
    if ($Warnings.Count -gt 0) {
        Write-Host "Warnings:" -ForegroundColor Yellow
        foreach ($Warning in $Warnings) {
            Write-Warning "  $Warning"
        }
        Write-Host ""
    }
    
    if ($Issues.Count -gt 0) {
        Write-Host "Please fix the issues above before starting development." -ForegroundColor Red
    } else {
        Write-Host "Backend is functional but some warnings should be addressed." -ForegroundColor Yellow
    }
}

Write-Host "============================================================`n" -ForegroundColor Cyan

# Exit with appropriate code
if ($Issues.Count -gt 0) {
    exit 1
} else {
    exit 0
}
