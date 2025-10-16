"""
Services package for business logic components.

Exposes Supabase-backed service abstractions for routers/tests while keeping
legacy service modules (S3 upload, billing, etc.) available under explicit
aliases.
"""

from .supabase import (
    ProfileService,
    JobService as _SupabaseJobService,
    UploadService as _SupabaseUploadService,
    CreditService,
    supabase_client,
)
from .auth import AuthService
from .billing import BillingService
from .uploads import UploadService as S3UploadService
from .jobs import JobService as LegacyJobService
from .entitlements import EntitlementsService

# Default exports use Supabase implementations
JobService = _SupabaseJobService
UploadService = _SupabaseUploadService

__all__ = [
    'AuthService',
    'BillingService',
    'CreditService',
    'EntitlementsService',
    'JobService',
    'LegacyJobService',
    'ProfileService',
    'S3UploadService',
    'supabase_client',
    'UploadService',
]
