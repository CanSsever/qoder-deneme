"""
End-to-End tests for provider integration and switching.

Tests the provider abstraction layer, configuration switching,
and provider-specific behavior differences.
"""

import pytest
from unittest.mock import patch, AsyncMock
from sqlmodel import Session

from apps.core.settings import settings
from apps.db.session import engine
from apps.db.models.job import Job
from apps.db.models.user import User
from apps.worker.tasks import process_ai_job
from apps.worker.providers.base import ProviderStatus
from tests.mocks.providers import MockProviderFactory, patch_providers_for_testing


class TestE2EProviderSwitching:
    """Test switching between different GPU providers."""
    
    @pytest.fixture
    def test_user(self):
        """Create test user."""
        with Session(engine) as session:
            user = User(
                email="provider-test@example.com",
                hashed_password="test_hash",
                credits=100
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    
    @pytest.fixture
    def test_job(self, test_user):
        """Create test job."""
        with Session(engine) as session:
            job = Job(
                user_id=test_user.id,
                job_type="face_restore",
                status="pending",
                params={
                    "input_url": "https://example.com/test.jpg",
                    "face_restore": "gfpgan",
                    "enhance": True
                }
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return job
    
    @pytest.mark.asyncio
    async def test_comfy_ui_provider_selection(self, test_job):
        """Test job processing with ComfyUI provider."""
        job_id = str(test_job.id)
        mock_providers = patch_providers_for_testing("success")
        
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'mock_comfy_local'), \
             patch('apps.worker.tasks.security_validator') as mock_validator, \
             patch('apps.worker.tasks.s3_service') as mock_s3:
            
            mock_validator.validate_image_url.return_value = {
                'mime_type': 'image/jpeg',
                'dimensions': (512, 512),
                'file_size': 150000,
                'content_hash': 'test_hash'
            }
            
            mock_validator.validate_image_content.return_value = {
                'mime_type': 'image/png',
                'dimensions': (1024, 1024),
                'file_size': 300000,
                'content_hash': 'output_hash'
            }
            
            mock_s3.upload_file_async.return_value = "https://s3.example.com/comfy-output.png"
            
            # Process with ComfyUI
            result = process_ai_job(job_id)
            
            # Verify ComfyUI provider was used
            comfy_provider = mock_providers['mock_comfy_local']
            runpod_provider = mock_providers['mock_runpod']
            
            assert len(comfy_provider.submitted_jobs) == 1
            assert len(runpod_provider.submitted_jobs) == 0
            assert result["status"] == "succeeded"
    
    @pytest.mark.asyncio
    async def test_runpod_provider_selection(self, test_job):
        """Test job processing with RunPod provider."""
        job_id = str(test_job.id)
        mock_providers = patch_providers_for_testing("success")
        
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'mock_runpod'), \
             patch('apps.worker.tasks.security_validator') as mock_validator, \
             patch('apps.worker.tasks.s3_service') as mock_s3:
            
            mock_validator.validate_image_url.return_value = {
                'mime_type': 'image/jpeg',
                'dimensions': (512, 512),
                'file_size': 150000,
                'content_hash': 'test_hash'
            }
            
            mock_validator.validate_image_content.return_value = {
                'mime_type': 'image/png',
                'dimensions': (1024, 1024),
                'file_size': 300000,
                'content_hash': 'output_hash'
            }
            
            mock_s3.upload_file_async.return_value = "https://s3.example.com/runpod-output.png"
            
            # Process with RunPod
            result = process_ai_job(job_id)
            
            # Verify RunPod provider was used
            comfy_provider = mock_providers['mock_comfy_local']
            runpod_provider = mock_providers['mock_runpod']
            
            assert len(comfy_provider.submitted_jobs) == 0
            assert len(runpod_provider.submitted_jobs) == 1
            assert result["status"] == "succeeded"
    
    @pytest.mark.asyncio
    async def test_unknown_provider_error(self, test_job):
        """Test error handling for unknown provider."""
        job_id = str(test_job.id)
        mock_providers = patch_providers_for_testing("success")
        
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'unknown_provider'):
            
            # Process with unknown provider
            result = process_ai_job(job_id)
            
            # Verify error
            assert result["status"] == "failed"
            assert "unknown provider" in result.get("error", "").lower()


class TestE2EProviderDifferences:
    """Test provider-specific behavior differences."""
    
    @pytest.fixture
    def test_user(self):
        """Create test user."""
        with Session(engine) as session:
            user = User(
                email="differences-test@example.com",
                hashed_password="test_hash", 
                credits=100
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    
    @pytest.mark.asyncio
    async def test_comfy_vs_runpod_remote_id_format(self, test_user):
        """Test different remote ID formats between providers."""
        with Session(engine) as session:
            job = Job(
                user_id=test_user.id,
                job_type="face_restore",
                status="pending",
                params={"input_url": "https://example.com/test.jpg"}
            )
            session.add(job)
            session.commit()
            session.refresh(job)
        
        mock_providers = patch_providers_for_testing("success")
        
        # Test ComfyUI remote ID format
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'mock_comfy_local'), \
             patch('apps.worker.tasks.security_validator') as mock_validator, \
             patch('apps.worker.tasks.s3_service') as mock_s3:
            
            mock_validator.validate_image_url.return_value = {
                'mime_type': 'image/jpeg',
                'dimensions': (512, 512),
                'file_size': 150000,
                'content_hash': 'test_hash'
            }
            
            mock_validator.validate_image_content.return_value = {
                'mime_type': 'image/png',
                'dimensions': (1024, 1024),
                'file_size': 300000,
                'content_hash': 'output_hash'
            }
            
            mock_s3.upload_file_async.return_value = "https://s3.example.com/output.png"
            
            # Process job
            process_ai_job(str(job.id))
            
            # Check ComfyUI remote ID format (UUID)
            comfy_provider = mock_providers['mock_comfy_local']
            comfy_remote_ids = list(comfy_provider.submitted_jobs.keys())
            assert len(comfy_remote_ids) == 1
            comfy_id = comfy_remote_ids[0]
            assert len(comfy_id.split('-')) == 5  # UUID format
        
        # Reset job for RunPod test
        with Session(engine) as session:
            job = session.get(Job, job.id)
            job.status = "pending"
            job.remote_id = None
            session.commit()
        
        # Reset mock providers
        mock_providers = patch_providers_for_testing("success")
        
        # Test RunPod remote ID format
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'mock_runpod'), \
             patch('apps.worker.tasks.security_validator') as mock_validator, \
             patch('apps.worker.tasks.s3_service') as mock_s3:
            
            mock_validator.validate_image_url.return_value = {
                'mime_type': 'image/jpeg',
                'dimensions': (512, 512),
                'file_size': 150000,
                'content_hash': 'test_hash'
            }
            
            mock_validator.validate_image_content.return_value = {
                'mime_type': 'image/png',
                'dimensions': (1024, 1024),
                'file_size': 300000,
                'content_hash': 'output_hash'
            }
            
            mock_s3.upload_file_async.return_value = "https://s3.example.com/output.png"
            
            # Process job
            process_ai_job(str(job.id))
            
            # Check RunPod remote ID format (runpod- prefix)
            runpod_provider = mock_providers['mock_runpod']
            runpod_remote_ids = list(runpod_provider.submitted_jobs.keys())
            assert len(runpod_remote_ids) == 1
            runpod_id = runpod_remote_ids[0]
            assert runpod_id.startswith('runpod-')
    
    @pytest.mark.asyncio
    async def test_provider_progress_reporting_differences(self, test_user):
        """Test different progress reporting patterns between providers."""
        # This test checks that both providers can report progress correctly
        # even though they have different internal implementations
        
        comfy_provider = MockProviderFactory.create_comfy_provider("success")
        runpod_provider = MockProviderFactory.create_runpod_provider("success")
        
        # Create mock job
        job = Job(
            id="test-progress-job",
            user_id=test_user.id,
            job_type="face_restore",
            status="pending",
            params={"input_url": "https://example.com/test.jpg"}
        )
        
        pipeline_config = {"test": "config"}
        
        # Test ComfyUI progress (increments by 20)
        comfy_response = await comfy_provider.submit(job, pipeline_config)
        comfy_remote_id = comfy_response.remote_id
        
        comfy_progress_sequence = []
        for _ in range(6):  # Should reach 100% after 5 polls
            poll_response = await comfy_provider.poll(job, comfy_remote_id)
            comfy_progress_sequence.append(poll_response.progress)
            if poll_response.progress >= 100:
                break
        
        # Test RunPod progress (increments by 33)
        runpod_response = await runpod_provider.submit(job, pipeline_config)
        runpod_remote_id = runpod_response.remote_id
        
        runpod_progress_sequence = []
        for _ in range(5):  # Should reach 100% after 3-4 polls
            poll_response = await runpod_provider.poll(job, runpod_remote_id)
            runpod_progress_sequence.append(poll_response.progress)
            if poll_response.progress >= 100:
                break
        
        # Verify both reach 100% but with different patterns
        assert max(comfy_progress_sequence) == 100
        assert max(runpod_progress_sequence) == 100
        
        # ComfyUI should have more granular progress updates
        assert len(comfy_progress_sequence) >= len(runpod_progress_sequence)
    
    @pytest.mark.asyncio
    async def test_provider_output_url_differences(self, test_user):
        """Test different output URL patterns between providers."""
        comfy_provider = MockProviderFactory.create_comfy_provider("success")
        runpod_provider = MockProviderFactory.create_runpod_provider("success")
        
        job = Job(
            id="test-output-job",
            user_id=test_user.id,
            job_type="upscale",
            status="pending",
            params={"input_url": "https://example.com/test.jpg"}
        )
        
        pipeline_config = {"test": "config"}
        
        # Test ComfyUI output URLs
        comfy_response = await comfy_provider.submit(job, pipeline_config)
        
        # Poll until completion
        while True:
            poll_response = await comfy_provider.poll(job, comfy_response.remote_id)
            if poll_response.status == ProviderStatus.SUCCEEDED:
                comfy_urls = poll_response.output_urls
                break
            if poll_response.progress >= 100:
                break
        
        # Test RunPod output URLs
        runpod_response = await runpod_provider.submit(job, pipeline_config)
        
        # Poll until completion
        while True:
            poll_response = await runpod_provider.poll(job, runpod_response.remote_id)
            if poll_response.status == ProviderStatus.SUCCEEDED:
                runpod_urls = poll_response.output_urls
                break
            if poll_response.progress >= 100:
                break
        
        # Verify URL patterns
        assert len(comfy_urls) > 0
        assert len(runpod_urls) > 0
        assert "mock-comfy.example.com" in comfy_urls[0]
        assert "mock-runpod-outputs.example.com" in runpod_urls[0]
    
    @pytest.mark.asyncio
    async def test_provider_download_output_differences(self, test_user):
        """Test different output file naming between providers."""
        comfy_provider = MockProviderFactory.create_comfy_provider("success")
        runpod_provider = MockProviderFactory.create_runpod_provider("success")
        
        test_urls = ["https://example.com/output.png"]
        
        # Test ComfyUI download outputs
        comfy_outputs = await comfy_provider.download_outputs("test-id", test_urls)
        
        # Test RunPod download outputs
        runpod_outputs = await runpod_provider.download_outputs("test-id", test_urls)
        
        # Verify different naming patterns
        comfy_keys = list(comfy_outputs.keys())
        runpod_keys = list(runpod_outputs.keys())
        
        assert len(comfy_keys) > 0
        assert len(runpod_keys) > 0
        
        # ComfyUI uses "output_0" pattern, RunPod uses "runpod_output_0"
        assert comfy_keys[0].startswith("output_")
        assert runpod_keys[0].startswith("runpod_output_")
        
        # Both should return valid image data
        assert len(comfy_outputs[comfy_keys[0]]) > 0
        assert len(runpod_outputs[runpod_keys[0]]) > 0
        
        # PNG header check
        assert comfy_outputs[comfy_keys[0]].startswith(b'\x89PNG')
        assert runpod_outputs[runpod_keys[0]].startswith(b'\x89PNG')


class TestE2EProviderErrorScenarios:
    """Test provider-specific error scenarios."""
    
    @pytest.fixture
    def test_user(self):
        """Create test user."""
        with Session(engine) as session:
            user = User(
                email="error-test@example.com",
                hashed_password="test_hash",
                credits=50
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    
    @pytest.mark.asyncio
    async def test_comfy_network_error_simulation(self, test_user):
        """Test ComfyUI network error handling."""
        with Session(engine) as session:
            job = Job(
                user_id=test_user.id,
                job_type="face_restore",
                status="pending",
                params={"input_url": "https://example.com/test.jpg"}
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = str(job.id)
        
        # Mock ComfyUI with network error
        mock_providers = {
            "mock_comfy_local": MockProviderFactory.create_comfy_provider("network_error"),
            "mock_runpod": MockProviderFactory.create_runpod_provider("success")
        }
        
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'mock_comfy_local'), \
             patch('apps.worker.tasks.security_validator') as mock_validator:
            
            mock_validator.validate_image_url.return_value = {
                'mime_type': 'image/jpeg',
                'dimensions': (512, 512),
                'file_size': 150000,
                'content_hash': 'test_hash'
            }
            
            # Process job - should fail due to network error
            result = process_ai_job(job_id)
            
            # Verify error handling
            assert result["status"] == "failed"
            assert "network" in result.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_runpod_api_error_simulation(self, test_user):
        """Test RunPod API error handling."""
        with Session(engine) as session:
            job = Job(
                user_id=test_user.id,
                job_type="upscale",
                status="pending",
                params={"input_url": "https://example.com/test.jpg"}
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = str(job.id)
        
        # Mock RunPod with API error
        mock_providers = {
            "mock_comfy_local": MockProviderFactory.create_comfy_provider("success"),
            "mock_runpod": MockProviderFactory.create_runpod_provider("network_error")
        }
        
        with patch('apps.worker.tasks.PROVIDERS', mock_providers), \
             patch('apps.worker.tasks.settings.gpu_provider', 'mock_runpod'), \
             patch('apps.worker.tasks.security_validator') as mock_validator:
            
            mock_validator.validate_image_url.return_value = {
                'mime_type': 'image/jpeg',
                'dimensions': (512, 512),
                'file_size': 150000,
                'content_hash': 'test_hash'
            }
            
            # Process job - should fail due to API error
            result = process_ai_job(job_id)
            
            # Verify error handling
            assert result["status"] == "failed"
            assert "runpod api" in result.get("error", "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])