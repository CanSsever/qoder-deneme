"""
Mock providers for E2E testing of the OneShot Face Swapper Backend.

These mock providers simulate ComfyUI and RunPod behavior without requiring
actual GPU infrastructure, enabling comprehensive testing of the provider
abstraction layer and job processing pipeline.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock

from apps.worker.providers.base import IProvider, ProviderResponse, ProviderStatus, ProviderError, ProviderTimeoutError
from apps.db.models.job import Job


class MockComfyUIProvider(IProvider):
    """
    Mock ComfyUI provider for testing.
    
    Simulates the behavior of ComfyUI local provider with configurable
    responses for different test scenarios.
    """
    
    def __init__(self, test_scenario: str = "success"):
        """
        Initialize mock provider with test scenario.
        
        Args:
            test_scenario: Test scenario to simulate
                - "success": Normal successful processing
                - "timeout": Simulate timeout error
                - "failure": Simulate processing failure
                - "network_error": Simulate network connectivity issues
        """
        self.name = "mock_comfy_local"
        self.test_scenario = test_scenario
        self.submitted_jobs = {}
        self.job_progress = {}
        
    async def submit(self, job: Job, pipeline_config: Dict[str, Any]) -> ProviderResponse:
        """Submit job for processing (mock)."""
        remote_id = str(uuid.uuid4())
        
        if self.test_scenario == "network_error":
            raise ProviderError("Network connection failed", self.name, remote_id)
        
        # Store job for tracking
        self.submitted_jobs[remote_id] = {
            "job": job,
            "pipeline_config": pipeline_config,
            "submitted_at": datetime.utcnow(),
            "status": ProviderStatus.SUBMITTED
        }
        
        self.job_progress[remote_id] = 0
        
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.SUBMITTED,
            message="Job submitted successfully",
            progress=0,
            output_urls=[]
        )
    
    async def poll(self, job: Job, remote_id: str) -> ProviderResponse:
        """Poll job status (mock)."""
        if remote_id not in self.submitted_jobs:
            raise ProviderError("Job not found", self.name, remote_id)
        
        job_info = self.submitted_jobs[remote_id]
        
        if self.test_scenario == "timeout":
            raise ProviderTimeoutError("Polling timeout", self.name, remote_id)
        
        if self.test_scenario == "failure":
            return ProviderResponse(
                remote_id=remote_id,
                status=ProviderStatus.FAILED,
                message="Processing failed due to invalid input",
                progress=50,
                output_urls=[]
            )
        
        # Simulate progressive completion
        current_progress = self.job_progress.get(remote_id, 0)
        if current_progress < 100:
            self.job_progress[remote_id] = min(current_progress + 20, 100)
        
        progress = self.job_progress[remote_id]
        
        if progress >= 100:
            job_info["status"] = ProviderStatus.SUCCEEDED
            output_urls = [
                f"https://mock-comfy.example.com/outputs/{remote_id}/output.png"
            ]
        else:
            job_info["status"] = ProviderStatus.RUNNING
            output_urls = []
        
        return ProviderResponse(
            remote_id=remote_id,
            status=job_info["status"],
            message=f"Processing at {progress}%",
            progress=progress,
            output_urls=output_urls
        )
    
    async def cancel(self, job: Job, remote_id: str) -> ProviderResponse:
        """Cancel job (mock)."""
        if remote_id in self.submitted_jobs:
            self.submitted_jobs[remote_id]["status"] = ProviderStatus.CANCELLED
        
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.CANCELLED,
            message="Job cancelled successfully",
            progress=self.job_progress.get(remote_id, 0),
            output_urls=[]
        )
    
    async def download_outputs(self, remote_id: str, output_urls: List[str]) -> Dict[str, bytes]:
        """Download output files (mock)."""
        # Generate mock image data (minimal PNG)
        mock_png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10'
            b'\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x19tEXtSoftware\x00'
            b'Adobe ImageReadyq\xc9e<\x00\x00\x00\x0eIDATx\xdac\xf8\x0f\x00\x00'
            b'\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        
        outputs = {}\n        for i, url in enumerate(output_urls):
            filename = f"output_{i}"
            outputs[filename] = mock_png_data
        
        return outputs


class MockRunPodProvider(IProvider):
    """
    Mock RunPod provider for testing.
    
    Simulates the behavior of RunPod serverless provider with configurable
    responses for different test scenarios.
    """
    
    def __init__(self, test_scenario: str = "success"):
        """
        Initialize mock provider with test scenario.
        
        Args:
            test_scenario: Test scenario to simulate (same as MockComfyUIProvider)
        """
        self.name = "mock_runpod"
        self.test_scenario = test_scenario
        self.submitted_jobs = {}
        self.job_progress = {}
        
    async def submit(self, job: Job, pipeline_config: Dict[str, Any]) -> ProviderResponse:
        """Submit job for processing (mock)."""
        remote_id = f"runpod-{uuid.uuid4()}"
        
        if self.test_scenario == "network_error":
            raise ProviderError("RunPod API unavailable", self.name, remote_id)
        
        # Store job for tracking
        self.submitted_jobs[remote_id] = {
            "job": job,
            "pipeline_config": pipeline_config,
            "submitted_at": datetime.utcnow(),
            "status": ProviderStatus.SUBMITTED
        }
        
        self.job_progress[remote_id] = 0
        
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.SUBMITTED,
            message="RunPod job queued",
            progress=0,
            output_urls=[]
        )
    
    async def poll(self, job: Job, remote_id: str) -> ProviderResponse:
        """Poll job status (mock)."""
        if remote_id not in self.submitted_jobs:
            raise ProviderError("RunPod job not found", self.name, remote_id)
        
        job_info = self.submitted_jobs[remote_id]
        
        if self.test_scenario == "timeout":
            raise ProviderTimeoutError("RunPod polling timeout", self.name, remote_id)
        
        if self.test_scenario == "failure":
            return ProviderResponse(
                remote_id=remote_id,
                status=ProviderStatus.FAILED,
                message="RunPod execution failed: GPU out of memory",
                progress=30,
                output_urls=[]
            )
        
        # Simulate progressive completion (faster than ComfyUI)
        current_progress = self.job_progress.get(remote_id, 0)
        if current_progress < 100:
            self.job_progress[remote_id] = min(current_progress + 33, 100)
        
        progress = self.job_progress[remote_id]
        
        if progress >= 100:
            job_info["status"] = ProviderStatus.SUCCEEDED
            output_urls = [
                f"https://mock-runpod-outputs.example.com/{remote_id}/result.png"
            ]
        else:
            job_info["status"] = ProviderStatus.RUNNING
            output_urls = []
        
        return ProviderResponse(
            remote_id=remote_id,
            status=job_info["status"],
            message=f"RunPod processing: {progress}% complete",
            progress=progress,
            output_urls=output_urls
        )
    
    async def cancel(self, job: Job, remote_id: str) -> ProviderResponse:
        """Cancel job (mock)."""
        if remote_id in self.submitted_jobs:
            self.submitted_jobs[remote_id]["status"] = ProviderStatus.CANCELLED
        
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.CANCELLED,
            message="RunPod job cancelled",
            progress=self.job_progress.get(remote_id, 0),
            output_urls=[]
        )
    
    async def download_outputs(self, remote_id: str, output_urls: List[str]) -> Dict[str, bytes]:
        """Download output files (mock)."""
        # Generate mock image data (different from ComfyUI for verification)
        mock_png_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x20\x00\x00\x00\x20'
            b'\x08\x06\x00\x00\x00sz\z\xf4\x00\x00\x00\x19tEXtSoftware\x00'
            b'RunPod Mock Provider\x00\x00\x00\x0eIDATx\xdac\xf8\x0f\x00\x00'
            b'\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        
        outputs = {}
        for i, url in enumerate(output_urls):
            filename = f"runpod_output_{i}"
            outputs[filename] = mock_png_data
        
        return outputs


class MockProviderFactory:
    """
    Factory for creating mock providers with different test scenarios.
    """
    
    @staticmethod
    def create_comfy_provider(scenario: str = "success") -> MockComfyUIProvider:
        """Create mock ComfyUI provider with specified scenario."""
        return MockComfyUIProvider(scenario)
    
    @staticmethod
    def create_runpod_provider(scenario: str = "success") -> MockRunPodProvider:
        """Create mock RunPod provider with specified scenario."""
        return MockRunPodProvider(scenario)
    
    @staticmethod
    def get_available_scenarios() -> List[str]:
        """Get list of available test scenarios."""
        return ["success", "timeout", "failure", "network_error"]


# Utility functions for test setup
def patch_providers_for_testing(test_scenario: str = "success"):
    """
    Create mock providers for testing.
    
    Args:
        test_scenario: Scenario to simulate
        
    Returns:
        Dict of mock providers
    """
    return {
        "mock_comfy_local": MockProviderFactory.create_comfy_provider(test_scenario),
        "mock_runpod": MockProviderFactory.create_runpod_provider(test_scenario)
    }


async def verify_mock_provider_behavior(provider: IProvider, test_scenario: str) -> Dict[str, Any]:
    """
    Verify mock provider behavior for testing.
    
    Args:
        provider: Mock provider instance
        test_scenario: Expected scenario
        
    Returns:
        Verification results
    """
    # Create mock job
    from apps.db.models.job import Job
    mock_job = Job(
        id="test-job-123",
        user_id="test-user",
        job_type="face_restore",
        status="pending",
        params={"input_url": "https://example.com/test.jpg"}
    )
    
    pipeline_config = {"test": "config"}
    
    try:
        # Test submission
        submit_response = await provider.submit(mock_job, pipeline_config)
        
        # Test polling
        poll_response = await provider.poll(mock_job, submit_response.remote_id)
        
        # Test cancellation
        cancel_response = await provider.cancel(mock_job, submit_response.remote_id)
        
        return {
            "provider_name": provider.name,
            "test_scenario": test_scenario,
            "submit_status": submit_response.status.value,
            "poll_status": poll_response.status.value,
            "cancel_status": cancel_response.status.value,
            "verification_passed": True
        }
        
    except Exception as e:
        return {
            "provider_name": provider.name,
            "test_scenario": test_scenario,
            "error": str(e),
            "verification_passed": False
        }