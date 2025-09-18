"""
Job model for AI processing tasks.
"""
from datetime import datetime
from typing import Dict, Optional, Any
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, JSON, Column
from apps.core.config import JobType, JobStatus


class JobBase(SQLModel):
    """Base job model with shared fields."""
    job_type: str = Field(description="Type of AI processing job")
    input_image_url: str = Field(description="URL of the input image")
    target_image_url: Optional[str] = Field(default=None, description="URL of target image for face swap")
    parameters: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON), description="Job parameters")


class Job(JobBase, table=True):
    """Job database model."""
    __tablename__ = "jobs"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    status: str = Field(default=JobStatus.PENDING)
    progress: float = Field(default=0.0, description="Job progress (0.0 to 1.0)")
    result_image_url: Optional[str] = Field(default=None, description="URL of the processed result image")
    credits_cost: int = Field(default=1, description="Credits consumed for this job")
    error_message: Optional[str] = Field(default=None, description="Error message if job failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None, description="When job processing started")
    finished_at: Optional[datetime] = Field(default=None, description="When job processing finished")
    completed_at: Optional[datetime] = Field(default=None)


class JobCreate(JobBase):
    """Job creation schema."""
    pass


class JobUpdate(SQLModel):
    """Job update schema."""
    status: Optional[str] = None
    progress: Optional[float] = None
    result_image_url: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


class JobRead(JobBase):
    """Job read schema (for API responses)."""
    id: UUID
    user_id: UUID
    status: str
    progress: float
    result_image_url: Optional[str]
    credits_cost: int
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class JobResponse(SQLModel):
    """Job creation response."""
    job_id: UUID
    status: str
    estimated_time: int
    credits_cost: int


class JobStatusResponse(SQLModel):
    """Job status response."""
    job_id: UUID
    status: str
    progress: float
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None