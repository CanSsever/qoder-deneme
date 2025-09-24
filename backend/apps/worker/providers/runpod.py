"""
RunPod serverless provider implementation.
"""
import asyncio
import json
import aiohttp
import time
from typing import Dict, Any, Optional
import structlog

from apps.core.settings import settings
from apps.db.models.job import Job
from .base import (
    IProvider, 
    ProviderResponse, 
    ProviderStatus, 
    ProviderError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderValidationError
)

logger = structlog.get_logger(__name__)


class RunPodProvider(IProvider):
    """RunPod serverless provider implementation."""
    
    def __init__(self):
        self.api_key = settings.runpod_api_key
        self.endpoint_id = settings.runpod_endpoint_id
        self.base_url = "https://api.runpod.ai/v2"
        self.timeout = 600  # 10 minutes for serverless
        
    @property
    def name(self) -> str:
        return "runpod"
    
    async def submit(self, job: Job, pipeline_config: Dict[str, Any]) -> ProviderResponse:
        """Submit job to RunPod serverless endpoint."""
        try:
            # Prepare input payload for RunPod
            input_payload = await self._prepare_input(job, pipeline_config)
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{self.endpoint_id}/run"
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "input": input_payload,
                    "webhook": None  # We'll implement webhooks separately
                }
                
                logger.info(
                    "Submitting job to RunPod",
                    job_id=str(job.id),
                    provider=self.name,
                    endpoint_id=self.endpoint_id
                )
                
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ProviderError(
                            f"RunPod submission failed: {response.status} - {error_text}",
                            self.name
                        )
                    
                    result = await response.json()
                    
                    if "id" not in result:
                        raise ProviderError(
                            f"RunPod did not return job ID: {result}",
                            self.name
                        )
                    
                    run_id = result["id"]
                    status = result.get("status", "IN_QUEUE")
                    
                    logger.info(
                        "Job submitted to RunPod",
                        job_id=str(job.id),
                        provider=self.name,
                        run_id=run_id,
                        status=status
                    )
                    
                    return ProviderResponse(
                        remote_id=run_id,
                        status=self._map_runpod_status(status),
                        progress=0.0,
                        message=f"Job submitted to RunPod: {status}"
                    )
                    
        except aiohttp.ClientError as e:
            raise ProviderConnectionError(
                f"Failed to connect to RunPod: {str(e)}",
                self.name
            )
        except Exception as e:
            raise ProviderError(
                f"RunPod submission error: {str(e)}",
                self.name
            )
    
    async def poll(self, job: Job, remote_id: str) -> ProviderResponse:
        """Poll job status from RunPod."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{self.endpoint_id}/status/{remote_id}"
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 404:
                        return ProviderResponse(
                            remote_id=remote_id,
                            status=ProviderStatus.FAILED,
                            progress=0.0,
                            message="Job not found in RunPod"
                        )
                    
                    if response.status != 200:
                        raise ProviderError(
                            f"Failed to get RunPod status: {response.status}",
                            self.name,
                            remote_id
                        )
                    
                    result = await response.json()
                    
                    status = result.get("status", "UNKNOWN")
                    output = result.get("output")
                    error = result.get("error")
                    
                    # Calculate progress based on status
                    progress = self._calculate_progress(status)
                    
                    if status == "COMPLETED" and output:
                        # Extract output URLs from RunPod response
                        output_urls = await self._extract_runpod_outputs(output)
                        
                        return ProviderResponse(
                            remote_id=remote_id,
                            status=ProviderStatus.SUCCEEDED,
                            progress=100.0,
                            message="Job completed successfully",
                            output_urls=output_urls,
                            metadata={"runpod_output": output}
                        )
                    
                    elif status == "FAILED" or error:
                        error_msg = error or "Unknown RunPod error"
                        return ProviderResponse(
                            remote_id=remote_id,
                            status=ProviderStatus.FAILED,
                            progress=0.0,
                            message=f"RunPod error: {error_msg}"
                        )
                    
                    elif status == "CANCELLED":
                        return ProviderResponse(
                            remote_id=remote_id,
                            status=ProviderStatus.CANCELLED,
                            progress=0.0,
                            message="Job cancelled in RunPod"
                        )
                    
                    else:
                        # Job is still running or queued
                        mapped_status = self._map_runpod_status(status)
                        return ProviderResponse(
                            remote_id=remote_id,
                            status=mapped_status,
                            progress=progress,
                            message=f"RunPod status: {status}"
                        )
                    
        except aiohttp.ClientError as e:
            raise ProviderConnectionError(
                f"Failed to poll RunPod: {str(e)}",
                self.name,
                remote_id
            )
        except Exception as e:
            raise ProviderError(
                f"RunPod polling error: {str(e)}",
                self.name,
                remote_id
            )
    
    async def cancel(self, job: Job, remote_id: str) -> ProviderResponse:
        """Cancel job in RunPod."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{self.endpoint_id}/cancel/{remote_id}"
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                async with session.post(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status not in [200, 404]:
                        raise ProviderError(
                            f"Failed to cancel RunPod job: {response.status}",
                            self.name,
                            remote_id
                        )
                    
                    # Check if job was successfully cancelled
                    if response.status == 404:
                        message = "Job not found (may already be completed or cancelled)"
                    else:
                        result = await response.json()
                        message = result.get("message", "Job cancellation requested")
                    
                    logger.info(
                        "Job cancellation requested in RunPod",
                        job_id=str(job.id),
                        provider=self.name,
                        remote_id=remote_id,
                        message=message
                    )
                    
                    return ProviderResponse(
                        remote_id=remote_id,
                        status=ProviderStatus.CANCELLED,
                        progress=0.0,
                        message=message
                    )
                    
        except aiohttp.ClientError as e:
            raise ProviderConnectionError(
                f"Failed to cancel RunPod job: {str(e)}",
                self.name,
                remote_id
            )
        except Exception as e:
            raise ProviderError(
                f"RunPod cancellation error: {str(e)}",
                self.name,
                remote_id
            )
    
    async def download_outputs(self, remote_id: str, output_urls: Dict[str, str]) -> Dict[str, bytes]:
        """Download output files from RunPod URLs."""
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                for output_name, url in output_urls.items():
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status == 200:
                            content = await response.read()
                            results[output_name] = content
                            
                            logger.info(
                                "Downloaded RunPod output",
                                remote_id=remote_id,
                                output_name=output_name,
                                size_bytes=len(content)
                            )
                        else:
                            logger.error(
                                "Failed to download RunPod output",
                                remote_id=remote_id,
                                output_name=output_name,
                                status=response.status
                            )
            
            return results
            
        except Exception as e:
            raise ProviderError(
                f"Failed to download RunPod outputs: {str(e)}",
                self.name,
                remote_id
            )
    
    async def health_check(self) -> bool:
        """Check RunPod endpoint health."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{self.endpoint_id}"
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }
                
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
                    
        except Exception:
            return False
    
    def _map_runpod_status(self, runpod_status: str) -> ProviderStatus:
        """Map RunPod status to our internal status."""
        status_map = {
            "IN_QUEUE": ProviderStatus.PENDING,
            "IN_PROGRESS": ProviderStatus.RUNNING,
            "COMPLETED": ProviderStatus.SUCCEEDED,
            "FAILED": ProviderStatus.FAILED,
            "CANCELLED": ProviderStatus.CANCELLED,
            "TIMED_OUT": ProviderStatus.FAILED
        }
        return status_map.get(runpod_status, ProviderStatus.PENDING)
    
    def _calculate_progress(self, status: str) -> float:
        """Calculate progress percentage based on RunPod status."""
        progress_map = {
            "IN_QUEUE": 0.0,
            "IN_PROGRESS": 50.0,
            "COMPLETED": 100.0,
            "FAILED": 0.0,
            "CANCELLED": 0.0,
            "TIMED_OUT": 0.0
        }
        return progress_map.get(status, 0.0)
    
    async def _prepare_input(self, job: Job, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare input payload for RunPod."""
        input_data = {
            "pipeline_type": job.job_type,
            "pipeline_config": pipeline_config,
            "job_params": job.params or {},
            "job_id": str(job.id)
        }
        
        # Add input URLs
        if hasattr(job, 'source_url') and job.source_url:
            input_data["source_url"] = job.source_url
        if hasattr(job, 'target_url') and job.target_url:
            input_data["target_url"] = job.target_url
        
        return input_data
    
    async def _extract_runpod_outputs(self, output: Dict[str, Any]) -> Dict[str, str]:
        """Extract output URLs from RunPod response."""
        output_urls = {}
        
        # RunPod typically returns outputs in different formats
        # Handle common patterns
        
        if isinstance(output, dict):
            # Pattern 1: Direct URLs in output
            if "output_urls" in output:
                return output["output_urls"]
            
            # Pattern 2: Files with URLs
            if "files" in output:
                files = output["files"]
                if isinstance(files, list):
                    for i, file_url in enumerate(files):
                        output_urls[f"output_{i}"] = file_url
                elif isinstance(files, dict):
                    output_urls.update(files)
            
            # Pattern 3: Single output URL
            if "output_url" in output:
                output_urls["output"] = output["output_url"]
            
            # Pattern 4: Base64 or direct file data (convert to temporary URLs)
            if "image_data" in output or "result" in output:
                # For base64 data, we'd need to handle it differently
                # This is a placeholder for custom handling
                pass
        
        elif isinstance(output, str):
            # Single URL returned as string
            output_urls["output"] = output
        
        return output_urls