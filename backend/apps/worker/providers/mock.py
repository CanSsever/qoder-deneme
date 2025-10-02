"""
Simple mock provider for basic testing and fallback.
"""
import uuid
from typing import Dict, Any
from apps.worker.providers.base import IProvider, ProviderResponse, ProviderStatus
from apps.db.models.job import Job


class MockProvider(IProvider):
    """Simple mock provider for testing and development."""
    
    @property
    def name(self) -> str:
        return "mock"
    
    def restore(self, *, token: str, job: Dict) -> Dict:
        """Mock restore operation."""
        return {"output_path": "outputs/mock/restore.png"}
    
    def upscale(self, *, token: str, job: Dict) -> Dict:
        """Mock upscale operation."""
        return {"output_path": "outputs/mock/upscale.png"}
    
    # Legacy async methods for compatibility with existing worker system
    async def submit(self, job: Job, pipeline_config: Dict[str, Any]) -> ProviderResponse:
        """Submit job for processing (mock)."""
        remote_id = str(uuid.uuid4())
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.PENDING,
            progress=0,
            message="Mock job submitted"
        )
    
    async def poll(self, job: Job, remote_id: str) -> ProviderResponse:
        """Poll job status (mock)."""
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.SUCCEEDED,
            progress=100,
            message="Mock job completed",
            output_urls={"output": "https://mock.example.com/output.png"}
        )
    
    async def cancel(self, job: Job, remote_id: str) -> ProviderResponse:
        """Cancel job (mock)."""
        return ProviderResponse(
            remote_id=remote_id,
            status=ProviderStatus.CANCELLED,
            progress=0,
            message="Mock job cancelled"
        )
    
    async def download_outputs(self, remote_id: str, output_urls: Dict[str, str]) -> Dict[str, bytes]:
        """Download output files (mock)."""
        return {"output": b"mock_image_data"}