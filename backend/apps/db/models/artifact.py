"""
Artifacts model for storing job outputs.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text
import json


class ArtifactBase(SQLModel):
    """Base artifact model with shared fields."""
    artifact_type: str = Field(description="Type of artifact (image, video, etc.)")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    mime_type: Optional[str] = Field(default=None, description="MIME type of the file")
    extra_data: Optional[str] = Field(default=None, description="Additional metadata as JSON string")


class Artifact(ArtifactBase, table=True):
    """Artifact database model."""
    __tablename__ = "artifacts"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(foreign_key="jobs.id", index=True)
    output_url: str = Field(description="URL where the artifact is stored")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ArtifactCreate(ArtifactBase):
    """Artifact creation schema."""
    job_id: UUID
    output_url: str


class ArtifactRead(ArtifactBase):
    """Artifact read schema (for API responses)."""
    id: UUID
    job_id: UUID
    output_url: str
    created_at: datetime