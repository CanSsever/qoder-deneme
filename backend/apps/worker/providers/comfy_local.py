"""
ComfyUI local provider implementation.
"""
import asyncio
import json
import aiohttp
import hashlib
from typing import Dict, Any, Optional
from urllib.parse import urljoin
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


class ComfyUILocalProvider(IProvider):
    """Local ComfyUI provider implementation."""
    
    def __init__(self):
        self.base_url = settings.comfy_local_url
        self.timeout = 300  # 5 minutes default timeout
        self.poll_interval = 2  # 2 seconds between polls
        
    @property
    def name(self) -> str:
        return "comfy_local"
    
    async def submit(self, job: Job, pipeline_config: Dict[str, Any]) -> ProviderResponse:
        """Submit job to local ComfyUI instance."""
        try:
            # Prepare workflow from pipeline config
            workflow = await self._prepare_workflow(job, pipeline_config)
            
            # Submit to ComfyUI queue
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.base_url, "/prompt")
                
                # Generate client_id for tracking
                client_id = self._generate_client_id(job.id)
                
                payload = {
                    "prompt": workflow,
                    "client_id": client_id
                }
                
                logger.info(
                    "Submitting job to ComfyUI",
                    job_id=str(job.id),
                    provider=self.name,
                    url=url,
                    client_id=client_id
                )
                
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ProviderError(
                            f"ComfyUI submission failed: {response.status} - {error_text}",
                            self.name
                        )
                    
                    result = await response.json()
                    prompt_id = result.get("prompt_id")
                    
                    if not prompt_id:
                        raise ProviderError(
                            "ComfyUI did not return prompt_id",
                            self.name
                        )
                    
                    logger.info(
                        "Job submitted to ComfyUI",
                        job_id=str(job.id),
                        provider=self.name,
                        prompt_id=prompt_id
                    )
                    
                    return ProviderResponse(
                        remote_id=prompt_id,
                        status=ProviderStatus.PENDING,
                        progress=0.0,
                        message="Job submitted to ComfyUI queue"
                    )
                    
        except aiohttp.ClientError as e:
            raise ProviderConnectionError(
                f"Failed to connect to ComfyUI: {str(e)}",
                self.name
            )
        except Exception as e:
            raise ProviderError(
                f"ComfyUI submission error: {str(e)}",
                self.name
            )
    
    async def poll(self, job: Job, remote_id: str) -> ProviderResponse:
        """Poll job status from ComfyUI."""
        try:
            async with aiohttp.ClientSession() as session:
                # Check queue status
                queue_url = urljoin(self.base_url, "/queue")
                
                async with session.get(
                    queue_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        raise ProviderError(
                            f"Failed to get ComfyUI queue status: {response.status}",
                            self.name,
                            remote_id
                        )
                    
                    queue_data = await response.json()
                    
                    # Check if job is in queue
                    queue_running = queue_data.get("queue_running", [])
                    queue_pending = queue_data.get("queue_pending", [])
                    
                    # Check running queue
                    for item in queue_running:
                        if item[1] == remote_id:  # prompt_id
                            return ProviderResponse(
                                remote_id=remote_id,
                                status=ProviderStatus.RUNNING,
                                progress=50.0,  # Heuristic progress
                                message="Job is running in ComfyUI"
                            )
                    
                    # Check pending queue
                    for item in queue_pending:
                        if item[1] == remote_id:  # prompt_id
                            return ProviderResponse(
                                remote_id=remote_id,
                                status=ProviderStatus.PENDING,
                                progress=0.0,
                                message="Job is pending in ComfyUI queue"
                            )
                    
                    # Not in queue - check history for completion
                    history_url = urljoin(self.base_url, f"/history/{remote_id}")
                    
                    async with session.get(
                        history_url,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as hist_response:
                        if hist_response.status == 200:
                            history_data = await hist_response.json()
                            
                            if remote_id in history_data:
                                job_data = history_data[remote_id]
                                status = job_data.get("status", {})
                                
                                if status.get("completed", False):
                                    # Extract output URLs
                                    outputs = job_data.get("outputs", {})
                                    output_urls = await self._extract_output_urls(outputs)
                                    
                                    return ProviderResponse(
                                        remote_id=remote_id,
                                        status=ProviderStatus.SUCCEEDED,
                                        progress=100.0,
                                        message="Job completed successfully",
                                        output_urls=output_urls,
                                        metadata={"comfy_outputs": outputs}
                                    )
                                elif "error" in status:
                                    return ProviderResponse(
                                        remote_id=remote_id,
                                        status=ProviderStatus.FAILED,
                                        progress=0.0,
                                        message=f"ComfyUI error: {status['error']}"
                                    )
                        
                        # Job not found - might be failed or cancelled
                        return ProviderResponse(
                            remote_id=remote_id,
                            status=ProviderStatus.FAILED,
                            progress=0.0,
                            message="Job not found in ComfyUI queue or history"
                        )
                    
        except aiohttp.ClientError as e:
            raise ProviderConnectionError(
                f"Failed to poll ComfyUI: {str(e)}",
                self.name,
                remote_id
            )
        except Exception as e:
            raise ProviderError(
                f"ComfyUI polling error: {str(e)}",
                self.name,
                remote_id
            )
    
    async def cancel(self, job: Job, remote_id: str) -> ProviderResponse:
        """Cancel job in ComfyUI."""
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.base_url, "/queue")
                
                payload = {
                    "delete": [remote_id]
                }
                
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        raise ProviderError(
                            f"Failed to cancel ComfyUI job: {response.status}",
                            self.name,
                            remote_id
                        )
                    
                    logger.info(
                        "Job cancelled in ComfyUI",
                        job_id=str(job.id),
                        provider=self.name,
                        remote_id=remote_id
                    )
                    
                    return ProviderResponse(
                        remote_id=remote_id,
                        status=ProviderStatus.CANCELLED,
                        progress=0.0,
                        message="Job cancelled in ComfyUI"
                    )
                    
        except aiohttp.ClientError as e:
            raise ProviderConnectionError(
                f"Failed to cancel ComfyUI job: {str(e)}",
                self.name,
                remote_id
            )
        except Exception as e:
            raise ProviderError(
                f"ComfyUI cancellation error: {str(e)}",
                self.name,
                remote_id
            )
    
    async def download_outputs(self, remote_id: str, output_urls: Dict[str, str]) -> Dict[str, bytes]:
        """Download output files from ComfyUI."""
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                for output_name, url in output_urls.items():
                    # ComfyUI output URLs are relative to the server
                    full_url = urljoin(self.base_url, url) if not url.startswith('http') else url
                    
                    async with session.get(
                        full_url,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status == 200:
                            content = await response.read()
                            results[output_name] = content
                            
                            logger.info(
                                "Downloaded ComfyUI output",
                                remote_id=remote_id,
                                output_name=output_name,
                                size_bytes=len(content)
                            )
                        else:
                            logger.error(
                                "Failed to download ComfyUI output",
                                remote_id=remote_id,
                                output_name=output_name,
                                status=response.status
                            )
            
            return results
            
        except Exception as e:
            raise ProviderError(
                f"Failed to download ComfyUI outputs: {str(e)}",
                self.name,
                remote_id
            )
    
    async def health_check(self) -> bool:
        """Check ComfyUI health."""
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.base_url, "/queue")
                
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
                    
        except Exception:
            return False
    
    def _generate_client_id(self, job_id) -> str:
        """Generate unique client ID for ComfyUI tracking."""
        return f"oneshot_{hashlib.md5(str(job_id).encode()).hexdigest()[:8]}"
    
    async def _prepare_workflow(self, job: Job, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare ComfyUI workflow from pipeline config and job parameters."""
        workflow = pipeline_config.copy()
        
        # Replace placeholders in workflow with actual job parameters
        workflow_str = json.dumps(workflow)
        
        # Replace input URLs
        if hasattr(job, 'source_url') and job.source_url:
            workflow_str = workflow_str.replace("{{INPUT_URL}}", job.source_url)
        if hasattr(job, 'target_url') and job.target_url:
            workflow_str = workflow_str.replace("{{TARGET_URL}}", job.target_url)
        
        # Replace parameters
        if job.params:
            for key, value in job.params.items():
                placeholder = f"{{{{{key.upper()}}}}}"
                workflow_str = workflow_str.replace(placeholder, str(value))
        
        return json.loads(workflow_str)
    
    async def _extract_output_urls(self, outputs: Dict[str, Any]) -> Dict[str, str]:
        """Extract output URLs from ComfyUI response."""
        output_urls = {}
        
        for node_id, node_outputs in outputs.items():
            if isinstance(node_outputs, dict):
                for output_type, files in node_outputs.items():
                    if isinstance(files, list):
                        for i, file_info in enumerate(files):
                            if isinstance(file_info, dict) and "filename" in file_info:
                                # ComfyUI typically serves outputs at /view?filename=xxx
                                filename = file_info["filename"]
                                output_url = f"/view?filename={filename}"
                                output_key = f"{output_type}_{i}" if i > 0 else output_type
                                output_urls[output_key] = output_url
        
        return output_urls