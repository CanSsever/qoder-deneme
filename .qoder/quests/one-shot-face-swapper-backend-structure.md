# OneShot Face Swapper Backend Architecture Design

## Overview

OneShot is a Face Swapper/Face Restoration application that allows users to upload photos and apply AI-powered face enhancement, face swapping, and upscaling using LoRA-based models (GFPGAN, CodeFormer, custom Face LoRAs). The backend is built with FastAPI and follows a job queue architecture to handle computationally intensive AI processing tasks.

**Key Features:**
- Face restoration and enhancement
- Face swapping capabilities  
- Image upscaling
- User authentication and onboarding
- Credit-based payment system
- Subscription management via Superwall integration
- Asynchronous job processing

**Technology Stack:**
- **Framework:** FastAPI + SQLModel + Uvicorn
- **Database:** PostgreSQL with Alembic migrations
- **Job Queue:** Background task processing
- **Storage:** S3-compatible storage for images
- **Authentication:** JWT-based authentication
- **Payment:** Superwall receipt validation

## Architecture

### System Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        Mobile[Expo React Native App]
        Superwall[Superwall SDK]
    end
    
    subgraph "API Gateway"
        FastAPI[FastAPI Application]
        Auth[Authentication Middleware]
        CORS[CORS Middleware]
    end
    
    subgraph "Business Logic"
        AuthService[Auth Service]
        JobService[Job Service]
        BillingService[Billing Service]
        UploadService[Upload Service]
    end
    
    subgraph "Data Layer"
        PostgreSQL[(PostgreSQL Database)]
        S3[S3 Storage]
    end
    
    subgraph "Processing Layer"
        JobQueue[Job Queue System]
        AIWorker[AI Processing Worker]
        LoRAModels[LoRA Models<br/>GFPGAN, CodeFormer]
    end
    
    Mobile --> FastAPI
    Superwall --> BillingService
    FastAPI --> Auth
    FastAPI --> AuthService
    FastAPI --> JobService
    FastAPI --> BillingService
    FastAPI --> UploadService
    
    AuthService --> PostgreSQL
    JobService --> PostgreSQL
    JobService --> JobQueue
    BillingService --> PostgreSQL
    UploadService --> S3
    
    JobQueue --> AIWorker
    AIWorker --> LoRAModels
    AIWorker --> S3
    AIWorker --> PostgreSQL
```

### Directory Structure

```
oneshot-backend/
├── apps/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── jobs.py
│   │       ├── uploads.py
│   │       └── billing.py
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── tasks.py
│   │   └── processors/
│   │       ├── __init__.py
│   │       ├── face_restoration.py
│   │       ├── face_swap.py
│   │       └── upscale.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── settings.py
│   │   ├── security.py
│   │   └── exceptions.py
│   └── db/
│       ├── __init__.py
│       ├── session.py
│       ├── base.py
│       └── models/
│           ├── __init__.py
│           ├── user.py
│           ├── job.py
│           ├── credit.py
│           └── subscription.py
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── script.py.mako
│   └── alembic.ini
├── requirements.txt
├── .env.example
├── main.py
└── alembic.ini
```

## API Endpoints Reference

### Authentication Endpoints

#### POST /auth/login
**Purpose:** User authentication via email or token

**Request Schema:**
```json
{
  "email": "user@example.com",
  "password": "string"
}
```

**Response Schema:**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "string",
    "credits": 10
  }
}
```

#### GET /auth/me
**Purpose:** Get current user information

**Authentication:** Required (Bearer Token)

**Response Schema:**
```json
{
  "id": "uuid",
  "email": "string",
  "credits": 10,
  "subscription_status": "active|inactive",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Upload Endpoints

#### POST /uploads/presign
**Purpose:** Generate S3 presigned URL for image upload

**Authentication:** Required

**Request Schema:**
```json
{
  "filename": "image.jpg",
  "content_type": "image/jpeg",
  "file_size": 1024000
}
```

**Response Schema:**
```json
{
  "presigned_url": "string",
  "upload_id": "uuid",
  "expires_in": 3600
}
```

### Job Processing Endpoints

#### POST /jobs
**Purpose:** Create new AI processing job

**Authentication:** Required

**Request Schema:**
```json
{
  "job_type": "face_restoration|face_swap|upscale",
  "input_image_url": "string",
  "target_image_url": "string", // Optional, for face swap
  "parameters": {
    "model": "gfpgan|codeformer|custom_lora",
    "scale_factor": 2,
    "face_enhance": true
  }
}
```

**Response Schema:**
```json
{
  "job_id": "uuid",
  "status": "pending",
  "estimated_time": 120,
  "credits_cost": 1
}
```

#### GET /jobs/{job_id}
**Purpose:** Get job status and progress

**Authentication:** Required

**Response Schema:**
```json
{
  "job_id": "uuid",
  "status": "pending|processing|completed|failed",
  "progress": 0.75,
  "result_url": "string", // Available when completed
  "error_message": "string", // Available when failed
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:02:00Z"
}
```

### Billing Endpoints

#### POST /billing/validate
**Purpose:** Validate Superwall receipt and add credits

**Authentication:** Required

**Request Schema:**
```json
{
  "receipt_data": "string",
  "product_id": "string",
  "transaction_id": "string"
}
```

**Response Schema:**
```json
{
  "valid": true,
  "credits_added": 50,
  "subscription_status": "active",
  "expires_at": "2024-02-01T00:00:00Z"
}
```

## Data Models & ORM Mapping

### User Model
```python
class User(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    credits: int = Field(default=10)
    subscription_status: str = Field(default="inactive")
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Job Model
```python
class Job(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    job_type: str  # face_restoration, face_swap, upscale
    status: str = Field(default="pending")  # pending, processing, completed, failed
    progress: float = Field(default=0.0)
    input_image_url: str
    target_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    parameters: dict = Field(default_factory=dict)
    credits_cost: int = Field(default=1)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
```

### Credit Transaction Model
```python
class CreditTransaction(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    amount: int  # Positive for additions, negative for usage
    transaction_type: str  # purchase, usage, bonus
    reference_id: Optional[str] = None  # Job ID or receipt ID
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Subscription Model
```python
class Subscription(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    product_id: str
    transaction_id: str = Field(unique=True)
    receipt_data: str
    status: str  # active, expired, cancelled
    credits_included: int
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

## Business Logic Layer

### Authentication Service Architecture

```mermaid
graph LR
    AuthRouter[Auth Router] --> AuthService[Auth Service]
    AuthService --> UserModel[User Model]
    AuthService --> JWTHandler[JWT Handler]
    AuthService --> PasswordHash[Password Hasher]
    
    subgraph "Auth Flow"
        Login[Login Request] --> Validate[Validate Credentials]
        Validate --> GenerateToken[Generate JWT]
        GenerateToken --> Response[Auth Response]
    end
```

**Key Components:**
- Password hashing using bcrypt
- JWT token generation and validation
- User session management
- Initial credit allocation for new users

### Job Processing Service Architecture

```mermaid
graph TD
    JobRequest[Job Request] --> ValidateUser[Validate User & Credits]
    ValidateUser --> CreateJob[Create Job Record]
    CreateJob --> QueueJob[Queue Background Task]
    QueueJob --> Response[Job ID Response]
    
    subgraph "Background Processing"
        Worker[AI Worker] --> DownloadImage[Download Input Image]
        DownloadImage --> ProcessAI[Apply LoRA Model]
        ProcessAI --> UploadResult[Upload Result to S3]
        UploadResult --> UpdateJob[Update Job Status]
    end
    
    QueueJob --> Worker
```

**Job Types:**
1. **Face Restoration:** GFPGAN/CodeFormer for enhancing image quality
2. **Face Swap:** Custom LoRA models for face replacement
3. **Upscale:** Image super-resolution algorithms

### Billing Service Architecture

```mermaid
graph LR
    BillingRouter[Billing Router] --> BillingService[Billing Service]
    BillingService --> ReceiptValidator[Receipt Validator]
    BillingService --> CreditManager[Credit Manager]
    BillingService --> SubscriptionManager[Subscription Manager]
    
    subgraph "Validation Flow"
        Receipt[Superwall Receipt] --> Verify[Verify with Apple/Google]
        Verify --> AddCredits[Add Credits to User]
        AddCredits --> UpdateSubscription[Update Subscription]
    end
```

## Middleware & Interceptors

### Authentication Middleware
- JWT token validation
- User context injection
- Protected route enforcement

### CORS Middleware
- Mobile app origin allowance
- Preflight request handling

### Rate Limiting Middleware
- API call rate limiting per user
- Job submission throttling

### Error Handling Middleware
- Standardized error responses
- Logging and monitoring integration

## Configuration Management

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/oneshot` |
| `S3_BUCKET` | S3 bucket name | `oneshot-images` |
| `S3_KEY` | AWS access key | `AKIA...` |
| `S3_SECRET` | AWS secret key | `abc123...` |
| `JWT_SECRET` | JWT signing secret | `your-secret-key` |
| `STRIPE_SECRET` | Stripe API secret | `sk_test_...` |
| `REDIS_URL` | Redis connection for job queue | `redis://localhost:6379` |

### Settings Configuration

```python
class Settings(BaseSettings):
    database_url: str
    s3_bucket: str
    s3_key: str
    s3_secret: str
    jwt_secret: str
    stripe_secret: str
    redis_url: str = "redis://localhost:6379"
    jwt_expiration_hours: int = 24
    max_file_size_mb: int = 10
    default_credits: int = 10
    
    class Config:
        env_file = ".env"
```

## Testing Strategy

### Unit Testing Structure

```
tests/
├── test_auth/
│   ├── test_auth_service.py
│   ├── test_jwt_handler.py
│   └── test_password_hash.py
├── test_jobs/
│   ├── test_job_service.py
│   ├── test_job_queue.py
│   └── test_ai_processors.py
├── test_billing/
│   ├── test_billing_service.py
│   ├── test_receipt_validation.py
│   └── test_credit_manager.py
└── test_api/
    ├── test_auth_endpoints.py
    ├── test_job_endpoints.py
    ├── test_upload_endpoints.py
    └── test_billing_endpoints.py
```

### Test Categories

1. **Unit Tests:** Individual service and utility function testing
2. **Integration Tests:** Database and external service integration
3. **API Tests:** Endpoint behavior and response validation
4. **Performance Tests:** Load testing for AI processing pipeline

### Test Configuration

- Test database isolation
- Mock external services (S3, Superwall)
- AI model mocking for faster test execution
- Fixture management for test data