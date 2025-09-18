"""
Custom exception classes and error handling utilities.
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class OneShotException(Exception):
    """Base exception class for OneShot application."""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(OneShotException):
    """Authentication related errors."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class AuthorizationError(OneShotException):
    """Authorization related errors."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


class ValidationError(OneShotException):
    """Data validation errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )


class NotFoundError(OneShotException):
    """Resource not found errors."""
    
    def __init__(self, resource: str, identifier: str = ""):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND
        )


class InsufficientCreditsError(OneShotException):
    """Insufficient credits for operation."""
    
    def __init__(self, required: int, available: int):
        super().__init__(
            message=f"Insufficient credits. Required: {required}, Available: {available}",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            details={"required_credits": required, "available_credits": available}
        )


class JobProcessingError(OneShotException):
    """Job processing related errors."""
    
    def __init__(self, message: str, job_id: Optional[str] = None):
        details = {"job_id": job_id} if job_id else {}
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class FileUploadError(OneShotException):
    """File upload related errors."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class PaymentError(OneShotException):
    """Payment and billing related errors."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED
        )


class RateLimitError(OneShotException):
    """Rate limiting errors."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class ExternalServiceError(OneShotException):
    """External service integration errors."""
    
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} service error: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service}
        )


# Exception handlers
async def oneshot_exception_handler(request: Request, exc: OneShotException) -> JSONResponse:
    """Global exception handler for OneShot exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": exc.__class__.__name__,
                "details": exc.details,
                "status_code": exc.status_code
            }
        }
    )


async def validation_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for validation errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "ValidationError",
                "status_code": exc.status_code
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unexpected exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error",
                "type": "InternalServerError",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
            }
        }
    )