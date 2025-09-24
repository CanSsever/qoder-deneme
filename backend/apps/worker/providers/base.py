"""
Base provider interface for GPU inference services.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

from apps.db.models.job import Job


class ProviderStatus(str, Enum):
    """Provider job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProviderResponse:
    """Standardized provider response."""
    remote_id: str
    status: ProviderStatus
    progress: float = 0.0
    message: Optional[str] = None
    output_urls: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class ProviderError(Exception):
    """Base provider error."""
    def __init__(self, message: str, provider: str, remote_id: Optional[str] = None):
        self.message = message
        self.provider = provider
        self.remote_id = remote_id
        super().__init__(f"{provider}: {message}")


class ProviderTimeoutError(ProviderError):
    """Provider timeout error."""
    pass


class ProviderConnectionError(ProviderError):
    """Provider connection error."""
    pass


class ProviderValidationError(ProviderError):
    """Provider validation error."""
    pass


class IProvider(ABC):
    """Abstract base class for GPU inference providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        pass
    
    @abstractmethod
    async def submit(self, job: Job, pipeline_config: Dict[str, Any]) -> ProviderResponse:
        """
        Submit a job to the provider.
        
        Args:
            job: Job instance containing input parameters
            pipeline_config: Pipeline configuration from JSON files
            
        Returns:
            ProviderResponse with remote_id and initial status
            
        Raises:
            ProviderError: On submission failure
        """
        pass
    
    @abstractmethod
    async def poll(self, job: Job, remote_id: str) -> ProviderResponse:
        """
        Poll job status from the provider.
        
        Args:
            job: Job instance
            remote_id: Remote job identifier from submit()
            
        Returns:
            ProviderResponse with current status and progress
            
        Raises:
            ProviderError: On polling failure
        """
        pass
    
    @abstractmethod
    async def cancel(self, job: Job, remote_id: str) -> ProviderResponse:
        """
        Cancel a running job.
        
        Args:
            job: Job instance
            remote_id: Remote job identifier
            
        Returns:
            ProviderResponse with cancelled status
            
        Raises:
            ProviderError: On cancellation failure
        """
        pass
    
    @abstractmethod
    async def download_outputs(self, remote_id: str, output_urls: Dict[str, str]) -> Dict[str, bytes]:
        """
        Download output files from the provider.
        
        Args:
            remote_id: Remote job identifier
            output_urls: Dictionary of output file URLs
            
        Returns:
            Dictionary mapping output names to file contents
            
        Raises:
            ProviderError: On download failure
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation - can be overridden
            return True
        except Exception:
            return False