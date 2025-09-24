"""
Application configuration constants and enums.
"""
from enum import Enum


class JobType(str, Enum):
    """Job types for AI processing."""
    FACE_RESTORATION = "face_restoration"
    FACE_SWAP = "face_swap"
    UPSCALE = "upscale"


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubscriptionStatus(str, Enum):
    """User subscription status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TransactionType(str, Enum):
    """Credit transaction types."""
    PURCHASE = "purchase"
    USAGE = "usage"
    BONUS = "bonus"
    REFUND = "refund"


class AIModel(str, Enum):
    """Available AI models for processing."""
    GFPGAN = "gfpgan"
    CODEFORMER = "codeformer"
    CUSTOM_LORA = "custom_lora"


# Credit costs for different operations
CREDIT_COSTS = {
    JobType.FACE_RESTORATION: 1,
    JobType.FACE_SWAP: 2,
    JobType.UPSCALE: 1,
}

# Supported image formats
SUPPORTED_IMAGE_FORMATS = ["jpg", "jpeg", "png", "webp"]

# Maximum image dimensions
MAX_IMAGE_WIDTH = 2048
MAX_IMAGE_HEIGHT = 2048

# Job processing timeouts (in seconds)
JOB_TIMEOUTS = {
    JobType.FACE_RESTORATION: 300,  # 5 minutes
    JobType.FACE_SWAP: 600,         # 10 minutes
    JobType.UPSCALE: 180,           # 3 minutes
}