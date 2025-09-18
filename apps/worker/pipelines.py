"""
Pipeline management and parameter validation for AI processing.
"""
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class PipelineType(str, Enum):
    """Supported pipeline types."""
    FACE_RESTORE = "face_restore"
    FACE_SWAP = "face_swap"
    UPSCALE = "upscale"


class FaceRestoreModel(str, Enum):
    """Face restoration models."""
    GFPGAN = "gfpgan"
    CODEFORMER = "codeformer"


class UpscaleModel(str, Enum):
    """Upscaling models."""
    REALESRGAN_X4PLUS = "realesrgan_x4plus"
    ULTRASHARP_4X = "4x_ultrasharp"


class OutputFormat(str, Enum):
    """Output image formats."""
    PNG = "png"
    JPEG = "jpeg"


class FaceRestoreParams(BaseModel):
    """Face restoration parameters."""
    face_restore: FaceRestoreModel = Field(default=FaceRestoreModel.GFPGAN)
    enhance: bool = Field(default=True)
    max_side: int = Field(default=1024, ge=256, le=2048)
    denoise: float = Field(default=0.5, ge=0.0, le=1.0)
    
    @validator('max_side')
    def validate_max_side(cls, v):
        """Ensure max_side is a power of 2 or common size."""
        valid_sizes = [256, 512, 768, 1024, 1536, 2048]
        if v not in valid_sizes:
            raise ValueError(f"max_side must be one of {valid_sizes}")
        return v


class FaceSwapParams(BaseModel):
    """Face swap parameters."""
    src_face_url: str = Field(..., description="Source face image URL")
    target_url: str = Field(..., description="Target image URL")
    lora: Optional[str] = Field(default=None, description="LoRA model name")
    blend: float = Field(default=0.8, ge=0.0, le=1.0, description="Blend ratio")
    max_side: int = Field(default=1024, ge=256, le=2048)
    
    @validator('src_face_url', 'target_url')
    def validate_urls(cls, v):
        """Validate URLs are not empty."""
        if not v or not v.strip():
            raise ValueError("URLs cannot be empty")
        return v.strip()
    
    @validator('max_side')
    def validate_max_side(cls, v):
        """Ensure max_side is a power of 2 or common size."""
        valid_sizes = [256, 512, 768, 1024, 1536, 2048]
        if v not in valid_sizes:
            raise ValueError(f"max_side must be one of {valid_sizes}")
        return v


class UpscaleParams(BaseModel):
    """Upscaling parameters."""
    model: UpscaleModel = Field(default=UpscaleModel.REALESRGAN_X4PLUS)
    scale: int = Field(default=2, description="Scale factor")
    tile: int = Field(default=0, description="Tile size for processing")
    
    @validator('scale')
    def validate_scale(cls, v):
        """Validate scale factor."""
        if v not in [2, 4]:
            raise ValueError("Scale must be 2 or 4")
        return v
    
    @validator('tile')
    def validate_tile(cls, v):
        """Validate tile size."""
        valid_tiles = [0, 256, 512]
        if v not in valid_tiles:
            raise ValueError(f"Tile size must be one of {valid_tiles}")
        return v


class PipelineManager:
    """Manages AI processing pipelines and parameter validation."""
    
    def __init__(self):
        self.pipelines_dir = Path(__file__).parent.parent.parent / "pipelines"
        self._pipeline_cache = {}
        
    def get_pipeline_config(self, pipeline_type: PipelineType) -> Dict[str, Any]:
        """Load pipeline configuration from JSON file."""
        if pipeline_type in self._pipeline_cache:
            return self._pipeline_cache[pipeline_type]
        
        pipeline_file = self.pipelines_dir / f"{pipeline_type.value}.json"
        
        if not pipeline_file.exists():
            raise ValueError(f"Pipeline file not found: {pipeline_file}")
        
        try:
            with open(pipeline_file, 'r') as f:
                config = json.load(f)
            
            self._pipeline_cache[pipeline_type] = config
            logger.info(
                "Loaded pipeline configuration",
                pipeline_type=pipeline_type.value,
                file=str(pipeline_file)
            )
            
            return config
            
        except Exception as e:
            logger.error(
                "Failed to load pipeline configuration",
                pipeline_type=pipeline_type.value,
                file=str(pipeline_file),
                error=str(e)
            )
            raise ValueError(f"Failed to load pipeline config: {e}")
    
    def validate_params(self, pipeline_type: PipelineType, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize parameters for a pipeline type."""
        try:
            if pipeline_type == PipelineType.FACE_RESTORE:
                validated = FaceRestoreParams(**params)
            elif pipeline_type == PipelineType.FACE_SWAP:
                validated = FaceSwapParams(**params)
            elif pipeline_type == PipelineType.UPSCALE:
                validated = UpscaleParams(**params)
            else:
                raise ValueError(f"Unknown pipeline type: {pipeline_type}")
            
            return validated.dict()
            
        except Exception as e:
            logger.error(
                "Parameter validation failed",
                pipeline_type=pipeline_type.value,
                params=params,
                error=str(e)
            )
            raise ValueError(f"Invalid parameters for {pipeline_type.value}: {e}")
    
    def prepare_pipeline_params(
        self,
        pipeline_type: PipelineType,
        params: Dict[str, Any],
        output_format: OutputFormat = OutputFormat.PNG
    ) -> Dict[str, Any]:
        """Prepare parameters for pipeline execution."""
        # Validate parameters first
        validated_params = self.validate_params(pipeline_type, params)
        
        # Create parameter mapping for template replacement
        param_map = {}
        
        # Common parameters
        param_map["OUTPUT_FORMAT"] = output_format.value
        
        # Pipeline-specific parameter mapping
        if pipeline_type == PipelineType.FACE_RESTORE:
            param_map.update({
                "FACE_RESTORE": validated_params["face_restore"],
                "ENHANCE": str(validated_params["enhance"]).lower(),
                "MAX_SIDE": str(validated_params["max_side"]),
                "DENOISE": str(validated_params["denoise"])
            })
            
        elif pipeline_type == PipelineType.FACE_SWAP:
            param_map.update({
                "SRC_FACE_URL": validated_params["src_face_url"],
                "TARGET_URL": validated_params["target_url"],
                "LORA": validated_params.get("lora", "none"),
                "BLEND": str(validated_params["blend"]),
                "MAX_SIDE": str(validated_params["max_side"])
            })
            
        elif pipeline_type == PipelineType.UPSCALE:
            param_map.update({
                "MODEL": validated_params["model"],
                "SCALE": str(validated_params["scale"]),
                "TILE": str(validated_params["tile"])
            })
        
        return param_map
    
    def get_available_pipelines(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available pipelines."""
        pipelines = {}
        
        for pipeline_type in PipelineType:
            try:
                config = self.get_pipeline_config(pipeline_type)
                pipelines[pipeline_type.value] = {
                    "type": pipeline_type.value,
                    "nodes": len(config),
                    "description": self._get_pipeline_description(pipeline_type)
                }
            except Exception as e:
                logger.warning(
                    "Failed to load pipeline info",
                    pipeline_type=pipeline_type.value,
                    error=str(e)
                )
        
        return pipelines
    
    def _get_pipeline_description(self, pipeline_type: PipelineType) -> str:
        """Get human-readable description of pipeline."""
        descriptions = {
            PipelineType.FACE_RESTORE: "Enhance and restore facial features in images",
            PipelineType.FACE_SWAP: "Swap faces between source and target images",
            PipelineType.UPSCALE: "Upscale images using AI super-resolution"
        }
        return descriptions.get(pipeline_type, "AI image processing pipeline")


# Global pipeline manager instance
pipeline_manager = PipelineManager()