"""
Data retention service for auto-deletion of old artifacts and job data.
"""
import os
import boto3
import structlog
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from apps.db.session import get_session
from apps.db.models.job import Job
from apps.db.models.artifact import Artifact
from apps.core.settings import settings

logger = structlog.get_logger(__name__)


class DataRetentionService:
    """Service for managing data retention and auto-deletion policies."""
    
    def __init__(self, retention_days: int = 30):
        """
        Initialize data retention service.
        
        Args:
            retention_days: Number of days to retain data before deletion
        """
        self.retention_days = retention_days
        self.s3_client = None
        
        # Initialize S3 client if credentials are available
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.s3_key,
                aws_secret_access_key=settings.s3_secret,
                region_name=settings.s3_region
            )
        except Exception as e:
            logger.warning("S3 client initialization failed", error=str(e))
    
    def run_retention_cleanup(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run data retention cleanup process.
        
        Args:
            dry_run: If True, only identify items for deletion without actually deleting
            
        Returns:
            Dictionary with cleanup results
        """
        cleanup_result = {
            "started_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "retention_days": self.retention_days,
            "jobs_processed": 0,
            "artifacts_deleted": 0,
            "s3_files_deleted": 0,
            "jobs_deleted": 0,
            "errors": [],
            "size_freed_bytes": 0
        }
        
        logger.info("Starting data retention cleanup", 
                   retention_days=self.retention_days,
                   dry_run=dry_run)
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            with Session(next(get_session())) as session:
                # Find jobs older than retention period
                old_jobs = self._find_expired_jobs(session, cutoff_date)
                cleanup_result["jobs_processed"] = len(old_jobs)
                
                logger.info("Found expired jobs", count=len(old_jobs), cutoff_date=cutoff_date.isoformat())
                
                # Process each expired job
                for job in old_jobs:
                    job_cleanup = self._cleanup_job_data(session, job, dry_run)
                    
                    cleanup_result["artifacts_deleted"] += job_cleanup["artifacts_deleted"]
                    cleanup_result["s3_files_deleted"] += job_cleanup["s3_files_deleted"]
                    cleanup_result["size_freed_bytes"] += job_cleanup["size_freed_bytes"]
                    cleanup_result["errors"].extend(job_cleanup["errors"])
                    
                    # Delete job record if all artifacts cleaned up successfully
                    if not dry_run and job_cleanup["cleanup_successful"]:
                        try:
                            session.delete(job)
                            cleanup_result["jobs_deleted"] += 1
                        except Exception as e:
                            error_msg = f"Failed to delete job {job.id}: {str(e)}"
                            cleanup_result["errors"].append(error_msg)
                            logger.error("Job deletion failed", job_id=str(job.id), error=str(e))
                
                # Commit changes if not dry run
                if not dry_run:
                    session.commit()
                    logger.info("Data retention cleanup committed")
                else:
                    logger.info("Dry run completed - no changes committed")
            
            cleanup_result["completed_at"] = datetime.utcnow().isoformat()
            cleanup_result["success"] = True
            
            logger.info("Data retention cleanup completed",
                       jobs_deleted=cleanup_result["jobs_deleted"],
                       artifacts_deleted=cleanup_result["artifacts_deleted"],
                       s3_files_deleted=cleanup_result["s3_files_deleted"],
                       size_freed_mb=cleanup_result["size_freed_bytes"] / (1024 * 1024),
                       errors_count=len(cleanup_result["errors"]))
            
        except Exception as e:
            cleanup_result["success"] = False
            cleanup_result["error"] = str(e)
            cleanup_result["completed_at"] = datetime.utcnow().isoformat()
            logger.error("Data retention cleanup failed", error=str(e))
        
        return cleanup_result
    
    def _find_expired_jobs(self, session: Session, cutoff_date: datetime) -> List[Job]:
        """Find jobs older than the cutoff date."""
        try:
            statement = select(Job).where(Job.created_at < cutoff_date)
            result = session.exec(statement)
            return list(result.all())
        except Exception as e:
            logger.error("Failed to find expired jobs", error=str(e))
            return []
    
    def _cleanup_job_data(self, session: Session, job: Job, dry_run: bool) -> Dict[str, Any]:
        """Clean up all data associated with a job."""
        job_cleanup = {
            "job_id": str(job.id),
            "artifacts_deleted": 0,
            "s3_files_deleted": 0,
            "size_freed_bytes": 0,
            "errors": [],
            "cleanup_successful": True
        }
        
        try:
            # Find all artifacts for this job
            artifacts_stmt = select(Artifact).where(Artifact.job_id == job.id)
            artifacts = list(session.exec(artifacts_stmt).all())
            
            logger.debug("Processing job artifacts", 
                        job_id=str(job.id), 
                        artifacts_count=len(artifacts))
            
            # Delete each artifact
            for artifact in artifacts:
                artifact_cleanup = self._cleanup_artifact(session, artifact, dry_run)
                
                job_cleanup["s3_files_deleted"] += artifact_cleanup["s3_files_deleted"]
                job_cleanup["size_freed_bytes"] += artifact_cleanup["size_freed_bytes"]
                job_cleanup["errors"].extend(artifact_cleanup["errors"])
                
                if artifact_cleanup["cleanup_successful"]:
                    if not dry_run:
                        session.delete(artifact)
                    job_cleanup["artifacts_deleted"] += 1
                else:
                    job_cleanup["cleanup_successful"] = False
            
            # Clean up input/output URLs from S3 if they exist
            urls_to_cleanup = []
            if job.input_image_url:
                urls_to_cleanup.append(job.input_image_url)
            if job.target_image_url:
                urls_to_cleanup.append(job.target_image_url)
            if job.result_image_url:
                urls_to_cleanup.append(job.result_image_url)
            
            for url in urls_to_cleanup:
                if self._is_s3_url(url):
                    s3_cleanup = self._delete_s3_file(url, dry_run)
                    if s3_cleanup["success"]:
                        job_cleanup["s3_files_deleted"] += 1
                        job_cleanup["size_freed_bytes"] += s3_cleanup.get("size_freed", 0)
                    else:
                        job_cleanup["errors"].append(s3_cleanup["error"])
                        job_cleanup["cleanup_successful"] = False
            
        except Exception as e:
            error_msg = f"Job cleanup failed for {job.id}: {str(e)}"
            job_cleanup["errors"].append(error_msg)
            job_cleanup["cleanup_successful"] = False
            logger.error("Job cleanup failed", job_id=str(job.id), error=str(e))
        
        return job_cleanup
    
    def _cleanup_artifact(self, session: Session, artifact: Artifact, dry_run: bool) -> Dict[str, Any]:
        """Clean up a single artifact and its S3 files."""
        artifact_cleanup = {
            "artifact_id": str(artifact.id),
            "s3_files_deleted": 0,
            "size_freed_bytes": 0,
            "errors": [],
            "cleanup_successful": True
        }
        
        try:
            # Delete S3 file if it exists
            if artifact.output_url and self._is_s3_url(artifact.output_url):
                s3_cleanup = self._delete_s3_file(artifact.output_url, dry_run)
                
                if s3_cleanup["success"]:
                    artifact_cleanup["s3_files_deleted"] = 1
                    artifact_cleanup["size_freed_bytes"] = s3_cleanup.get("size_freed", 0)
                else:
                    artifact_cleanup["errors"].append(s3_cleanup["error"])
                    artifact_cleanup["cleanup_successful"] = False
            
        except Exception as e:
            error_msg = f"Artifact cleanup failed for {artifact.id}: {str(e)}"
            artifact_cleanup["errors"].append(error_msg)
            artifact_cleanup["cleanup_successful"] = False
        
        return artifact_cleanup
    
    def _delete_s3_file(self, s3_url: str, dry_run: bool) -> Dict[str, Any]:
        """Delete a file from S3."""
        s3_result = {
            "success": False,
            "error": None,
            "size_freed": 0
        }
        
        if not self.s3_client:
            s3_result["error"] = "S3 client not available"
            return s3_result
        
        try:
            # Extract bucket and key from URL
            bucket, key = self._parse_s3_url(s3_url)
            
            if not bucket or not key:
                s3_result["error"] = f"Invalid S3 URL format: {s3_url}"
                return s3_result
            
            # Get file size before deletion
            try:
                response = self.s3_client.head_object(Bucket=bucket, Key=key)
                s3_result["size_freed"] = response.get('ContentLength', 0)
            except self.s3_client.exceptions.NoSuchKey:
                # File doesn't exist, consider it successfully "deleted"
                s3_result["success"] = True
                return s3_result
            except Exception:
                # Continue with deletion even if we can't get size
                pass
            
            # Delete the file
            if not dry_run:
                self.s3_client.delete_object(Bucket=bucket, Key=key)
                logger.debug("S3 file deleted", bucket=bucket, key=key)
            else:
                logger.debug("S3 file would be deleted (dry run)", bucket=bucket, key=key)
            
            s3_result["success"] = True
            
        except Exception as e:
            s3_result["error"] = f"S3 deletion failed for {s3_url}: {str(e)}"
            logger.error("S3 file deletion failed", url=s3_url, error=str(e))
        
        return s3_result
    
    def _is_s3_url(self, url: str) -> bool:
        """Check if URL is an S3 URL."""
        return url and (url.startswith('https://') and ('s3.' in url or 's3-' in url))
    
    def _parse_s3_url(self, s3_url: str) -> tuple:
        """Parse S3 URL to extract bucket and key."""
        try:
            # Handle different S3 URL formats
            if 's3.amazonaws.com' in s3_url:
                # Format: https://bucket.s3.amazonaws.com/key
                parts = s3_url.replace('https://', '').split('/')
                bucket = parts[0].split('.s3.amazonaws.com')[0]
                key = '/'.join(parts[1:]) if len(parts) > 1 else ''
            elif 's3.' in s3_url:
                # Format: https://s3.region.amazonaws.com/bucket/key
                parts = s3_url.replace('https://', '').split('/')
                bucket = parts[1] if len(parts) > 1 else ''
                key = '/'.join(parts[2:]) if len(parts) > 2 else ''
            else:
                return None, None
            
            return bucket, key
        except Exception:
            return None, None
    
    def get_retention_stats(self) -> Dict[str, Any]:
        """Get statistics about data eligible for retention cleanup."""
        stats = {
            "total_jobs": 0,
            "expired_jobs": 0,
            "total_artifacts": 0,
            "expired_artifacts": 0,
            "estimated_size_to_cleanup_mb": 0,
            "cutoff_date": None
        }
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            stats["cutoff_date"] = cutoff_date.isoformat()
            
            with Session(next(get_session())) as session:
                # Total jobs
                total_jobs_stmt = select(Job)
                stats["total_jobs"] = len(list(session.exec(total_jobs_stmt).all()))
                
                # Expired jobs
                expired_jobs_stmt = select(Job).where(Job.created_at < cutoff_date)
                expired_jobs = list(session.exec(expired_jobs_stmt).all())
                stats["expired_jobs"] = len(expired_jobs)
                
                # Total artifacts
                total_artifacts_stmt = select(Artifact)
                stats["total_artifacts"] = len(list(session.exec(total_artifacts_stmt).all()))
                
                # Expired artifacts
                expired_job_ids = [job.id for job in expired_jobs]
                if expired_job_ids:
                    expired_artifacts_stmt = select(Artifact).where(Artifact.job_id.in_(expired_job_ids))
                    expired_artifacts = list(session.exec(expired_artifacts_stmt).all())
                    stats["expired_artifacts"] = len(expired_artifacts)
                    
                    # Estimate size
                    total_size = sum(artifact.file_size or 0 for artifact in expired_artifacts)
                    stats["estimated_size_to_cleanup_mb"] = total_size / (1024 * 1024)
                
        except Exception as e:
            logger.error("Failed to get retention stats", error=str(e))
            stats["error"] = str(e)
        
        return stats