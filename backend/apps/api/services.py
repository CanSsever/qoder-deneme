"""
Authentication service for user management and JWT handling.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select
from apps.core.security import SecurityUtils
from apps.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from apps.core.settings import settings
from apps.db.models.user import User, UserCreate, UserLogin, UserResponse, UserRead
from apps.db.models.credit import CreditTransaction, CreditTransactionCreate
from apps.core.config import TransactionType
import boto3
from botocore.exceptions import ClientError
from uuid import uuid4
import os


class AuthService:
    """Authentication service for user management."""
    
    @staticmethod
    def create_user(session: Session, user_data: UserCreate) -> User:
        """Create a new user with hashed password."""
        # Check if user already exists
        statement = select(User).where(User.email == user_data.email)
        existing_user = session.exec(statement).first()
        if existing_user:
            raise ValidationError("Email already registered")
        
        # Create user with hashed password
        hashed_password = SecurityUtils.get_password_hash(user_data.password)
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            credits=settings.default_credits,
            subscription_status=user_data.subscription_status,
            subscription_expires_at=user_data.subscription_expires_at
        )
        
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create initial credit transaction
        credit_transaction = CreditTransaction(
            user_id=user.id,
            amount=settings.default_credits,
            transaction_type=TransactionType.BONUS,
            description="Welcome bonus credits"
        )
        session.add(credit_transaction)
        session.commit()
        
        return user
    
    @staticmethod
    def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        if not user:
            return None
        
        if not SecurityUtils.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    @staticmethod
    def login_user(session: Session, login_data: UserLogin) -> UserResponse:
        """Login user and return JWT token."""
        user = AuthService.authenticate_user(
            session, 
            login_data.email, 
            login_data.password
        )
        
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        # Create access token
        access_token = SecurityUtils.create_access_token(
            data={"sub": str(user.id)}
        )
        
        # Update last login time
        user.updated_at = datetime.utcnow()
        session.add(user)
        session.commit()
        session.refresh(user)
        
        return UserResponse(
            access_token=access_token,
            user=UserRead(
                id=user.id,
                email=user.email,
                credits=user.credits,
                subscription_status=user.subscription_status,
                subscription_expires_at=user.subscription_expires_at,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        )
    
    @staticmethod
    def get_user_by_id(session: Session, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        return session.get(User, user_id)
    
    @staticmethod
    def get_user_by_email(session: Session, email: str) -> Optional[User]:
        """Get user by email."""
        statement = select(User).where(User.email == email)
        return session.exec(statement).first()
    
    @staticmethod
    def update_user_credits(session: Session, user_id: UUID, credits_change: int, transaction_type: str, reference_id: Optional[str] = None) -> User:
        """Update user credits and create transaction record."""
        user = AuthService.get_user_by_id(session, user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        
        # Update user credits
        user.credits += credits_change
        user.updated_at = datetime.utcnow()
        session.add(user)
        
        # Create credit transaction
        credit_transaction = CreditTransaction(
            user_id=user_id,
            amount=credits_change,
            transaction_type=transaction_type,
            reference_id=reference_id
        )
        session.add(credit_transaction)
        
        session.commit()
        session.refresh(user)
        return user


class UploadService:
    """S3 upload service for handling file uploads."""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.s3_key,
            aws_secret_access_key=settings.s3_secret,
            region_name=settings.s3_region
        )
    
    def generate_presigned_url(
        self, 
        filename: str, 
        content_type: str, 
        file_size: int,
        expires_in: int = 3600
    ) -> dict:
        """Generate presigned URL for S3 upload."""
        # Validate file size
        max_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
        if file_size > max_size:
            raise ValidationError(f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB")
        
        # Validate content type
        if not content_type.startswith('image/'):
            raise ValidationError("Only image files are allowed")
        
        # Generate unique file key
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid4()}{file_extension}"
        file_key = f"uploads/{unique_filename}"
        
        try:
            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.s3_bucket,
                    'Key': file_key,
                    'ContentType': content_type
                },
                ExpiresIn=expires_in
            )
            
            return {
                "presigned_url": presigned_url,
                "upload_id": str(uuid4()),
                "file_key": file_key,
                "expires_in": expires_in
            }
            
        except ClientError as e:
            raise ValidationError(f"Failed to generate upload URL: {str(e)}")
    
    def get_file_url(self, file_key: str) -> str:
        """Get public URL for uploaded file."""
        return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{file_key}"


class JobService:
    """Job processing service for managing AI tasks."""
    
    @staticmethod
    def create_job(session: Session, user: User, job_data: 'JobCreate') -> 'Job':
        """Create a new AI processing job."""
        from apps.db.models.job import Job
        from apps.core.config import CREDIT_COSTS, JOB_TIMEOUTS
        
        # Check if user has enough credits
        credits_required = CREDIT_COSTS.get(job_data.job_type, 1)
        if user.credits < credits_required:
            from apps.core.exceptions import InsufficientCreditsError
            raise InsufficientCreditsError(credits_required, user.credits)
        
        # Create job record
        job = Job(
            user_id=user.id,
            job_type=job_data.job_type,
            input_image_url=job_data.input_image_url,
            target_image_url=job_data.target_image_url,
            parameters=job_data.parameters,
            credits_cost=credits_required
        )
        
        session.add(job)
        session.commit()
        session.refresh(job)
        
        # Deduct credits from user
        AuthService.update_user_credits(
            session, 
            user.id, 
            -credits_required, 
            TransactionType.USAGE,
            str(job.id)
        )
        
        # Queue background job (placeholder - would integrate with Celery)
        # queue_ai_processing_task.delay(str(job.id))
        
        return job
    
    @staticmethod
    def get_job(session: Session, job_id: UUID, user_id: UUID) -> Optional['Job']:
        """Get job by ID and user ID."""
        from apps.db.models.job import Job
        statement = select(Job).where(Job.id == job_id, Job.user_id == user_id)
        return session.exec(statement).first()
    
    @staticmethod
    def update_job_status(session: Session, job_id: UUID, status: str, progress: float = None, result_url: str = None, error_message: str = None) -> Optional['Job']:
        """Update job status and progress."""
        from apps.db.models.job import Job
        job = session.get(Job, job_id)
        if not job:
            return None
        
        job.status = status
        if progress is not None:
            job.progress = progress
        if result_url:
            job.result_image_url = result_url
        if error_message:
            job.error_message = error_message
        if status in ['completed', 'failed']:
            job.completed_at = datetime.utcnow()
        
        session.add(job)
        session.commit()
        session.refresh(job)
        return job
    
    @staticmethod
    def get_user_jobs(session: Session, user_id: UUID, skip: int = 0, limit: int = 10) -> list:
        """Get user's jobs with pagination."""
        from apps.db.models.job import Job
        statement = select(Job).where(Job.user_id == user_id).offset(skip).limit(limit).order_by(Job.created_at.desc())
        return session.exec(statement).all()


class BillingService:
    """Billing service for receipt validation and credit management."""
    
    @staticmethod
    def validate_receipt(session: Session, user: User, receipt_data: 'ReceiptValidation') -> 'ReceiptValidationResponse':
        """Validate Superwall receipt and add credits."""
        from apps.db.models.subscription import Subscription, ReceiptValidationResponse
        from apps.core.config import SubscriptionStatus
        import json
        import requests
        
        try:
            # Check if transaction already processed
            existing_subscription = session.query(Subscription).filter(
                Subscription.transaction_id == receipt_data.transaction_id
            ).first()
            
            if existing_subscription:
                return ReceiptValidationResponse(
                    valid=False,
                    credits_added=0,
                    subscription_status=user.subscription_status,
                    error_message="Transaction already processed"
                )
            
            # Validate receipt with Superwall/Apple/Google (simplified)
            # In production, this would make actual API calls to validate receipts
            is_valid = BillingService._validate_receipt_with_provider(receipt_data)
            
            if not is_valid:
                return ReceiptValidationResponse(
                    valid=False,
                    credits_added=0,
                    subscription_status=user.subscription_status,
                    error_message="Invalid receipt"
                )
            
            # Determine credits based on product ID
            credits_to_add = BillingService._get_credits_for_product(receipt_data.product_id)
            subscription_expires_at = datetime.utcnow() + timedelta(days=30)  # Default 30 days
            
            # Create subscription record
            subscription = Subscription(
                user_id=user.id,
                product_id=receipt_data.product_id,
                transaction_id=receipt_data.transaction_id,
                receipt_data=receipt_data.receipt_data,
                status=SubscriptionStatus.ACTIVE,
                credits_included=credits_to_add,
                expires_at=subscription_expires_at
            )
            
            session.add(subscription)
            
            # Add credits to user
            AuthService.update_user_credits(
                session,
                user.id,
                credits_to_add,
                TransactionType.PURCHASE,
                receipt_data.transaction_id
            )
            
            # Update user subscription status
            user.subscription_status = SubscriptionStatus.ACTIVE
            user.subscription_expires_at = subscription_expires_at
            user.updated_at = datetime.utcnow()
            session.add(user)
            
            session.commit()
            
            return ReceiptValidationResponse(
                valid=True,
                credits_added=credits_to_add,
                subscription_status=SubscriptionStatus.ACTIVE,
                expires_at=subscription_expires_at
            )
            
        except Exception as e:
            session.rollback()
            return ReceiptValidationResponse(
                valid=False,
                credits_added=0,
                subscription_status=user.subscription_status,
                error_message=f"Validation error: {str(e)}"
            )
    
    @staticmethod
    def _validate_receipt_with_provider(receipt_data: 'ReceiptValidation') -> bool:
        """Validate receipt with payment provider (placeholder implementation)."""
        # In production, this would make actual API calls to Apple/Google/Superwall
        # For now, return True for development
        return True
    
    @staticmethod
    def _get_credits_for_product(product_id: str) -> int:
        """Get credit amount based on product ID."""
        # Define product mappings
        product_credits = {
            "credits_10": 10,
            "credits_50": 50,
            "credits_100": 100,
            "subscription_monthly": 100,
            "subscription_yearly": 1200
        }
        return product_credits.get(product_id, 10)  # Default to 10 credits