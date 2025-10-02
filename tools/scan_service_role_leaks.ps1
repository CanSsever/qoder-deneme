# PowerShell version of scan_service_role_leaks.sh
param()

# Check if ripgrep is available, otherwise use Select-String
$RG = $null
if (Get-Command rg -ErrorAction SilentlyContinue) {
    $RG = "rg"
}

$violations = @()

if ($RG) {
    $rawResults = & $RG -n "service_client\(|Supa\.service\(\)" backend\apps 2>$null
    $violations = $rawResults | Where-Object { 
        $_ -notmatch "entitlements\.py" -and 
        $_ -notmatch "tools" -and 
        $_ -notmatch "invite_existing_users\.py" 
    }
} else {
    $serviceFiles = Get-ChildItem -Path "backend\apps" -Recurse -Include "*.py" |
        Select-String -Pattern "service_client\(|Supa\.service\(\)" 2>$null |
        Where-Object { 
            $_.Filename -notmatch "entitlements\.py" -and 
            $_.Path -notmatch "tools" -and 
            $_.Filename -notmatch "invite_existing_users\.py" 
        }
    $violations = $serviceFiles
}

if ($violations.Count -gt 0) {
    Write-Host "Service role found in user paths:" -ForegroundColor Red
    $violations | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    exit 1
} else {
    Write-Host "No service role leaks" -ForegroundColor Green
}