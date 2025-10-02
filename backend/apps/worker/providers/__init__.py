# Provider package initialization

import os
from .mock import MockProvider

def get_provider():
    """Get the configured provider instance."""
    name = os.getenv("MODEL_PROVIDER", "mock").lower()
    if name == "replicate":
        from .replicate import ReplicateProvider
        return ReplicateProvider()
    return MockProvider()