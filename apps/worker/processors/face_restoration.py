"""
Face restoration processor using GFPGAN and CodeFormer models.
"""
import os
import requests
from PIL import Image
from typing import Dict, Any
import tempfile
from apps.core.exceptions import JobProcessingError


class FaceRestorationProcessor:
    """Face restoration processor for enhancing image quality."""
    
    def __init__(self):
        self.model_cache = {}
    
    def process(self, input_image_url: str, parameters: Dict[str, Any]) -> str:
        """Process face restoration on input image."""
        try:
            # Download input image
            input_path = self._download_image(input_image_url)
            
            # Get model from parameters
            model = parameters.get("model", "gfpgan")
            scale_factor = parameters.get("scale_factor", 2)
            
            # Process image based on model
            if model == "gfpgan":
                output_path = self._process_gfpgan(input_path, scale_factor)
            elif model == "codeformer":
                output_path = self._process_codeformer(input_path, scale_factor)
            else:
                raise JobProcessingError(f"Unsupported model: {model}")
            
            # Upload result to S3 (placeholder - would use actual S3 upload)
            result_url = self._upload_result(output_path)
            
            # Cleanup temp files
            self._cleanup_files([input_path, output_path])
            
            return result_url
            
        except Exception as e:
            raise JobProcessingError(f"Face restoration failed: {str(e)}")
    
    def _download_image(self, image_url: str) -> str:
        """Download image from URL to temporary file."""
        response = requests.get(image_url)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(response.content)
            return tmp_file.name
    
    def _process_gfpgan(self, input_path: str, scale_factor: int) -> str:
        """Process image with GFPGAN model (placeholder implementation)."""
        # In production, this would use actual GFPGAN model
        # For now, just copy the input as output
        output_path = input_path.replace(".jpg", "_gfpgan.jpg")
        
        # Simulate processing
        image = Image.open(input_path)
        # Apply basic enhancement (placeholder for actual GFPGAN processing)
        enhanced_image = image.resize(
            (image.width * scale_factor, image.height * scale_factor),
            Image.Resampling.LANCZOS
        )
        enhanced_image.save(output_path, quality=95)
        
        return output_path
    
    def _process_codeformer(self, input_path: str, scale_factor: int) -> str:
        """Process image with CodeFormer model (placeholder implementation)."""
        # In production, this would use actual CodeFormer model
        output_path = input_path.replace(".jpg", "_codeformer.jpg")
        
        # Simulate processing
        image = Image.open(input_path)
        # Apply basic enhancement (placeholder for actual CodeFormer processing)
        enhanced_image = image.resize(
            (image.width * scale_factor, image.height * scale_factor),
            Image.Resampling.LANCZOS
        )
        enhanced_image.save(output_path, quality=95)
        
        return output_path
    
    def _upload_result(self, file_path: str) -> str:
        """Upload result image to S3 (placeholder implementation)."""
        # In production, this would upload to actual S3 bucket
        filename = os.path.basename(file_path)
        return f"https://oneshot-images.s3.amazonaws.com/results/{filename}"
    
    def _cleanup_files(self, file_paths: list):
        """Clean up temporary files."""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass  # Ignore cleanup errors