# PowerShell Database Backup Script for Windows
# Production database backup with validation and S3 upload

param(
    [string]$BackupDir = "C:\backups\postgres",
    [int]$RetentionDays = 30,
    [string]$DBHost = $env:DATABASE_HOST ?? "localhost",
    [string]$DBPort = $env:DATABASE_PORT ?? "5432",
    [string]$DBName = $env:DATABASE_NAME ?? "oneshot_prod",
    [string]$DBUser = $env:DATABASE_USER ?? "postgres",
    [string]$S3BackupBucket = $env:S3_BACKUP_BUCKET,
    [switch]$SkipS3Upload
)

# Configuration
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "oneshot_db_$Timestamp.sql"
$BackupPath = Join-Path $BackupDir $BackupFile
$LogFile = Join-Path $BackupDir "backup.log"

# Logging function
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $LogEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Write-Output $LogEntry
    Add-Content -Path $LogFile -Value $LogEntry
}

# Error handling
$ErrorActionPreference = "Stop"
trap {
    Write-Log "ERROR: $($_.Exception.Message)" "ERROR"
    if (Test-Path $BackupPath) {
        Remove-Item $BackupPath -Force
        Write-Log "Cleanup: Removed failed backup file" "INFO"
    }
    exit 1
}

try {
    # Create backup directory
    if (-not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }

    Write-Log "Starting database backup for $DBName"

    # Validate PostgreSQL tools
    $pgDumpPath = Get-Command "pg_dump.exe" -ErrorAction SilentlyContinue
    if (-not $pgDumpPath) {
        throw "pg_dump not found in PATH. Install PostgreSQL client tools."
    }

    # Test database connection
    $env:PGPASSWORD = $env:DATABASE_PASSWORD
    $testConnection = & "pg_isready.exe" -h $DBHost -p $DBPort -U $DBUser 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot connect to database $DBHost`:$DBPort - $testConnection"
    }

    Write-Log "Database connection validated"

    # Create backup
    Write-Log "Creating backup: $BackupFile"
    
    $pgDumpArgs = @(
        "--host=$DBHost",
        "--port=$DBPort", 
        "--username=$DBUser",
        "--dbname=$DBName",
        "--verbose",
        "--clean",
        "--if-exists",
        "--create",
        "--format=custom",
        "--compress=9",
        "--file=$BackupPath"
    )

    & "pg_dump.exe" @pgDumpArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }

    # Validate backup file
    if (-not (Test-Path $BackupPath) -or (Get-Item $BackupPath).Length -eq 0) {
        throw "Backup file is missing or empty"
    }

    $BackupSize = (Get-Item $BackupPath).Length
    $BackupSizeFormatted = "{0:N2} MB" -f ($BackupSize / 1MB)
    Write-Log "Backup created successfully: $BackupFile ($BackupSizeFormatted)"

    # Test backup integrity
    Write-Log "Validating backup integrity"
    & "pg_restore.exe" --list $BackupPath > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Backup file is corrupted"
    }
    Write-Log "Backup validation passed"

    # Upload to S3 if configured and not skipped
    if ($S3BackupBucket -and -not $SkipS3Upload) {
        Write-Log "Uploading backup to S3: s3://$S3BackupBucket/"
        
        $awsCmd = Get-Command "aws.exe" -ErrorAction SilentlyContinue
        if ($awsCmd) {
            $s3Key = "daily/$BackupFile"
            & "aws.exe" s3 cp $BackupPath "s3://$S3BackupBucket/$s3Key" --storage-class STANDARD_IA --metadata "backup-date=$Timestamp,database=$DBName"
            
            if ($LASTEXITCODE -eq 0) {
                Write-Log "S3 upload successful"
            } else {
                Write-Log "S3 upload failed" "WARNING"
            }
        } else {
            Write-Log "AWS CLI not found, skipping S3 upload" "WARNING"
        }
    }

    # Cleanup old backups
    Write-Log "Cleaning up backups older than $RetentionDays days"
    $CutoffDate = (Get-Date).AddDays(-$RetentionDays)
    $OldBackups = Get-ChildItem -Path $BackupDir -Name "oneshot_db_*.sql" | 
        Where-Object { (Get-Item (Join-Path $BackupDir $_)).CreationTime -lt $CutoffDate }

    foreach ($OldBackup in $OldBackups) {
        Remove-Item (Join-Path $BackupDir $OldBackup) -Force
        Write-Log "Removed old backup: $OldBackup"
    }

    # Rotate log file if too large (10MB)
    if ((Get-Item $LogFile -ErrorAction SilentlyContinue)?.Length -gt 10MB) {
        $LogBackup = "$LogFile.$(Get-Date -Format 'yyyyMMdd')"
        Move-Item $LogFile $LogBackup
        Write-Log "Log file rotated to $LogBackup"
    }

    # Generate backup report
    $BackupCount = (Get-ChildItem -Path $BackupDir -Name "oneshot_db_*.sql").Count
    $TotalSize = (Get-ChildItem -Path $BackupDir -Name "oneshot_db_*.sql" | 
        Measure-Object -Property Length -Sum).Sum
    $TotalSizeFormatted = "{0:N2} MB" -f ($TotalSize / 1MB)

    Write-Log "Backup completed successfully"
    Write-Log "Total backups: $BackupCount, Total size: $TotalSizeFormatted"

    # Send notification webhook if configured
    if ($env:BACKUP_WEBHOOK_URL) {
        $WebhookBody = @{
            status = "success"
            backup_file = $BackupFile
            backup_size = $BackupSizeFormatted
            timestamp = $Timestamp
            database = $DBName
        } | ConvertTo-Json

        try {
            Invoke-RestMethod -Uri $env:BACKUP_WEBHOOK_URL -Method Post -Body $WebhookBody -ContentType "application/json" | Out-Null
            Write-Log "Webhook notification sent"
        } catch {
            Write-Log "Webhook notification failed: $($_.Exception.Message)" "WARNING"
        }
    }

    Write-Log "Database backup process completed successfully"
    exit 0

} catch {
    Write-Log "FATAL ERROR: $($_.Exception.Message)" "ERROR"
    exit 1
} finally {
    # Cleanup environment
    $env:PGPASSWORD = $null
}