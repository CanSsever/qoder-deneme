#!/usr/bin/env python3
"""
Production Backup Verification Script
Validates backup integrity and retention policies
"""

import os
import sys
import json
import logging
import subprocess
import boto3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import psycopg2
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/log/backup-verification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackupVerifier:
    def __init__(self):
        self.backup_dir = os.getenv('BACKUP_DIR', '/backups/postgres')
        self.s3_bucket = os.getenv('S3_BACKUP_BUCKET')
        self.db_config = {
            'host': os.getenv('DATABASE_HOST', 'localhost'),
            'port': os.getenv('DATABASE_PORT', '5432'),
            'database': os.getenv('DATABASE_NAME', 'oneshot_prod'),
            'user': os.getenv('DATABASE_USER', 'postgres'),
            'password': os.getenv('DATABASE_PASSWORD')
        }
        self.s3_client = boto3.client('s3') if self.s3_bucket else None
        
    def verify_local_backups(self) -> Dict:
        """Verify local backup files"""
        logger.info("Verifying local backup files")
        
        backup_path = Path(self.backup_dir)
        if not backup_path.exists():
            logger.error(f"Backup directory does not exist: {self.backup_dir}")
            return {'status': 'error', 'message': 'Backup directory missing'}
        
        # Find backup files
        backup_files = list(backup_path.glob('oneshot_db_*.sql'))
        if not backup_files:
            logger.error("No backup files found")
            return {'status': 'error', 'message': 'No backup files found'}
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        verified_backups = []
        failed_backups = []
        
        for backup_file in backup_files[:5]:  # Check last 5 backups
            try:
                # Check file size
                file_size = backup_file.stat().st_size
                if file_size == 0:
                    failed_backups.append(f"{backup_file.name}: Empty file")
                    continue
                
                # Verify pg_restore can read the file
                result = subprocess.run(
                    ['pg_restore', '--list', str(backup_file)],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Calculate file hash for integrity
                    file_hash = self._calculate_file_hash(backup_file)
                    verified_backups.append({
                        'file': backup_file.name,
                        'size': file_size,
                        'size_mb': round(file_size / 1024 / 1024, 2),
                        'modified': datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
                        'hash': file_hash[:16]  # First 16 chars for logging
                    })
                    logger.info(f"✓ Verified: {backup_file.name} ({file_size / 1024 / 1024:.1f} MB)")
                else:
                    failed_backups.append(f"{backup_file.name}: {result.stderr}")
                    logger.error(f"✗ Failed: {backup_file.name} - {result.stderr}")
                    
            except Exception as e:
                failed_backups.append(f"{backup_file.name}: {str(e)}")
                logger.error(f"✗ Error verifying {backup_file.name}: {e}")
        
        return {
            'status': 'success' if verified_backups and not failed_backups else 'warning',
            'verified_count': len(verified_backups),
            'failed_count': len(failed_backups),
            'verified_backups': verified_backups,
            'failed_backups': failed_backups
        }
    
    def verify_s3_backups(self) -> Dict:
        """Verify S3 backup files"""
        if not self.s3_client or not self.s3_bucket:
            logger.info("S3 backup verification skipped (not configured)")
            return {'status': 'skipped', 'message': 'S3 not configured'}
        
        logger.info(f"Verifying S3 backups in bucket: {self.s3_bucket}")
        
        try:
            # List objects in the backup bucket
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket,
                Prefix='daily/',
                MaxKeys=10
            )
            
            if 'Contents' not in response:
                return {'status': 'warning', 'message': 'No S3 backups found'}
            
            # Sort by last modified (newest first)
            objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
            
            verified_s3_backups = []
            for obj in objects[:5]:  # Check last 5
                # Verify object exists and has size
                head_response = self.s3_client.head_object(
                    Bucket=self.s3_bucket,
                    Key=obj['Key']
                )
                
                verified_s3_backups.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'size_mb': round(obj['Size'] / 1024 / 1024, 2),
                    'last_modified': obj['LastModified'].isoformat(),
                    'storage_class': obj.get('StorageClass', 'STANDARD'),
                    'etag': head_response['ETag'].strip('"')[:16]
                })
                
                logger.info(f"✓ S3 Verified: {obj['Key']} ({obj['Size'] / 1024 / 1024:.1f} MB)")
            
            return {
                'status': 'success',
                'verified_count': len(verified_s3_backups),
                'verified_backups': verified_s3_backups
            }
            
        except Exception as e:
            logger.error(f"S3 verification failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def verify_retention_policy(self) -> Dict:
        """Verify backup retention policies are working"""
        logger.info("Verifying retention policy compliance")
        
        current_time = datetime.now()
        retention_days = int(os.getenv('RETENTION_DAYS', '30'))
        cutoff_date = current_time - timedelta(days=retention_days)
        
        backup_path = Path(self.backup_dir)
        old_backups = []
        
        for backup_file in backup_path.glob('oneshot_db_*.sql'):
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_time < cutoff_date:
                old_backups.append({
                    'file': backup_file.name,
                    'age_days': (current_time - file_time).days,
                    'should_be_deleted': True
                })
        
        if old_backups:
            logger.warning(f"Found {len(old_backups)} backups older than {retention_days} days")
            return {
                'status': 'warning',
                'message': f'Retention policy violation: {len(old_backups)} old backups found',
                'old_backups': old_backups,
                'retention_days': retention_days
            }
        else:
            logger.info("Retention policy compliance verified")
            return {
                'status': 'success',
                'message': 'Retention policy compliant',
                'retention_days': retention_days
            }
    
    def test_backup_restore(self, test_db_name: str = 'oneshot_backup_test') -> Dict:
        """Test backup restore functionality"""
        logger.info("Testing backup restore functionality")
        
        try:
            # Find the most recent backup
            backup_path = Path(self.backup_dir)
            backup_files = list(backup_path.glob('oneshot_db_*.sql'))
            if not backup_files:
                return {'status': 'error', 'message': 'No backup files to test'}
            
            latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
            logger.info(f"Testing restore of: {latest_backup.name}")
            
            # Create test database
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Drop test database if exists
            cursor.execute(f"DROP DATABASE IF EXISTS {test_db_name}")
            cursor.execute(f"CREATE DATABASE {test_db_name}")
            cursor.close()
            conn.close()
            
            # Restore backup to test database
            restore_cmd = [
                'pg_restore',
                '--host', self.db_config['host'],
                '--port', self.db_config['port'],
                '--username', self.db_config['user'],
                '--dbname', test_db_name,
                '--clean',
                '--if-exists',
                '--verbose',
                str(latest_backup)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_config['password']
            
            result = subprocess.run(restore_cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                # Verify restore by checking table count
                test_conn = psycopg2.connect(**{**self.db_config, 'database': test_db_name})
                test_cursor = test_conn.cursor()
                test_cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
                table_count = test_cursor.fetchone()[0]
                test_cursor.close()
                test_conn.close()
                
                # Cleanup test database
                conn = psycopg2.connect(**self.db_config)
                conn.autocommit = True
                cursor = conn.cursor()
                cursor.execute(f"DROP DATABASE {test_db_name}")
                cursor.close()
                conn.close()
                
                logger.info(f"✓ Restore test successful: {table_count} tables restored")
                return {
                    'status': 'success',
                    'backup_file': latest_backup.name,
                    'tables_restored': table_count,
                    'test_db': test_db_name
                }
            else:
                logger.error(f"Restore test failed: {result.stderr}")
                return {
                    'status': 'error',
                    'message': f'Restore failed: {result.stderr}',
                    'backup_file': latest_backup.name
                }
                
        except Exception as e:
            logger.error(f"Restore test error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def generate_report(self) -> Dict:
        """Generate comprehensive backup verification report"""
        logger.info("Generating backup verification report")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'local_backups': self.verify_local_backups(),
            's3_backups': self.verify_s3_backups(),
            'retention_policy': self.verify_retention_policy(),
            'restore_test': self.test_backup_restore()
        }
        
        # Calculate overall status
        statuses = [check['status'] for check in report.values() if isinstance(check, dict) and 'status' in check]
        if any(status == 'error' for status in statuses):
            report['overall_status'] = 'error'
        elif any(status == 'warning' for status in statuses):
            report['overall_status'] = 'warning'
        else:
            report['overall_status'] = 'success'
        
        return report

def main():
    """Main execution function"""
    verifier = BackupVerifier()
    report = verifier.generate_report()
    
    # Print summary
    print(f"\n📊 Backup Verification Report - {report['timestamp']}")
    print(f"Overall Status: {report['overall_status'].upper()}")
    print(f"Local Backups: {report['local_backups']['status']} ({report['local_backups'].get('verified_count', 0)} verified)")
    print(f"S3 Backups: {report['s3_backups']['status']} ({report['s3_backups'].get('verified_count', 0)} verified)")
    print(f"Retention Policy: {report['retention_policy']['status']}")
    print(f"Restore Test: {report['restore_test']['status']}")
    
    # Save full report
    report_file = f"/tmp/backup-verification-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"Full report saved to: {report_file}")
    
    # Exit with appropriate code
    if report['overall_status'] == 'error':
        sys.exit(1)
    elif report['overall_status'] == 'warning':
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()