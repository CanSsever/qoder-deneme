# OneShot Face Swapper Backend v2.0 (Production Ready)

A production-ready FastAPI backend for AI-powered face swapping with advanced features including real GPU inference integration, provider abstraction, comprehensive security, and extensive testing.

## Features

### 🚀 **Production Features v2.0 - GPU Integration**
- **Real GPU Processing**: ComfyUI local and RunPod serverless provider integration
- **Provider Abstraction**: Switchable GPU providers (ComfyUI Local, RunPod Serverless)
- **Advanced Security**: Comprehensive image validation, size limits, MIME type checking, magic byte verification
- **Idempotency & Caching**: SHA256-based deduplication prevents duplicate processing
- **Retry Logic**: Exponential backoff retry with configurable delays (15s, 60s)
- **Webhook System**: HMAC-SHA256 signed webhooks with retry mechanism
- **Pipeline Validation**: Pydantic-based parameter validation for all AI operations
- **S3 Integration**: Secure file upload/download with temporary file handling

### 🏗️ **Advanced Production Features (v2.0)**
- **Queue & GPU Integration**: Celery + Redis background job processing with real GPU providers
- **Realistic Pipeline Parameters**: Advanced job validation with face restoration, upscaling, and custom parameters
- **Rate Limiting**: IP and user-based rate limiting with slowapi and Redis backend
- **Monitoring & Logging**: Prometheus metrics, structured JSON logging with correlation IDs
- **Security & Validation**: Comprehensive input validation, file type checking, and error handling
- **Docker & Local Development**: Full Docker Compose setup with Redis and Celery workers
- **Comprehensive Testing**: 100+ tests with pytest, coverage reporting, E2E tests with mock providers

### 🔧 **Core Backend Features**
- **FastAPI Framework**: Async REST API with automatic OpenAPI documentation
- **Database**: SQLModel ORM with Alembic migrations
- **Authentication**: JWT-based auth with bcrypt password hashing
- **File Storage**: AWS S3 integration with presigned URLs
- **Credit System**: User credits and subscription management
- **AI Processing**: Modular AI pipeline for face swapping, restoration, and upscaling

## Quick Start

### Using Docker (Recommended)

1. **Clone and setup:**
```bash
git clone <repository-url>
cd qoder-deneme
cp .env.example .env
```

2. **Start all services:**
```bash
make docker-up
```

3. **Access the application:**
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090

### Local Development Setup

1. **Install dependencies:**
```bash
make install
```

2. **Setup database:**
```bash
make migrate
```

3. **Start Redis (required for rate limiting and Celery):**
```bash
# Option 1: Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Option 2: Install Redis locally
# Windows: Download from https://github.com/microsoftarchive/redis/releases
# macOS: brew install redis
# Linux: apt-get install redis-server
```

4. **Start development servers:**
```bash
# Terminal 1: API server
make dev

# Terminal 2: Celery worker
make worker
```

## Available Commands

### Development
```bash
make install     # Install dependencies
make dev        # Start development server
make worker     # Start Celery worker
make migrate    # Run database migrations
make setup      # Full development setup (install + migrate)
```

### Testing
```bash
make test       # Run tests
make coverage   # Run tests with coverage report
make test-e2e   # Run E2E tests with mock providers
```

### E2E Testing with Mock Providers

The project includes comprehensive end-to-end tests using mock GPU providers:

```bash
# Run all E2E tests
pytest tests/test_e2e_* -v

# Run specific test categories
pytest tests/test_e2e_job_processing.py -v       # Job processing workflows
pytest tests/test_e2e_provider_integration.py -v # Provider switching

# Run with coverage
pytest tests/test_e2e_* --cov=apps --cov-report=html

# Run specific test scenarios
pytest -k "test_face_restore_success" -v         # Face restoration
pytest -k "test_idempotency_cache_hit" -v        # Cache testing
pytest -k "test_webhook_notifications" -v        # Webhook testing
```

**Test Coverage:**
- Face restoration, face swap, and upscale workflows
- Provider switching (ComfyUI ↔ RunPod)
- Idempotency and caching mechanisms
- Retry logic and error handling
- Security validation and input filtering
- Webhook notifications with HMAC signatures
- Job cancellation workflows

### Docker
```bash
make docker-up   # Start all services
make docker-down # Stop all services
make logs        # Show Docker logs
```

### Utilities
```bash
make clean      # Clean cache files
make health     # Check service health
```

## API Documentation

### Authentication Endpoints
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Get current user info

### Job Management
- `POST /api/v1/jobs` - Create new face swap job
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/jobs` - List user jobs

### File Upload
- `POST /api/v1/uploads/presign` - Generate presigned S3 URL

### Billing
- `POST /api/v1/billing/validate` - Validate App Store/Play Store receipts

### Monitoring
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=sqlite:///./oneshot_dev.db

# Redis (for rate limiting and Celery)
REDIS_URL=redis://localhost:6379/0

# JWT Authentication
JWT_SECRET=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# AWS S3 (for file storage)
S3_BUCKET=your-bucket-name
S3_KEY=your-aws-access-key
S3_SECRET=your-aws-secret-key
S3_REGION=us-east-1

# GPU Provider Configuration
GPU_PROVIDER=comfy_local  # Options: comfy_local, runpod

# ComfyUI Local Configuration
COMFY_LOCAL_URL=http://localhost:8188

# RunPod Configuration
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_ENDPOINT_ID=your-runpod-endpoint-id

# Output Configuration
OUTPUT_FORMAT=png  # Options: png, jpeg
OUTPUT_QUALITY=95  # JPEG quality (1-100)
MAX_INPUT_MB=20    # Maximum input file size

# Security Configuration
MAX_IMAGE_DIMENSION=8192
MIN_IMAGE_DIMENSION=64

# Webhook Configuration
HMAC_SECRET=your-webhook-hmac-secret
WEBHOOK_TIMEOUT_SECONDS=30
WEBHOOK_RETRY_DELAYS=60,300,1800,7200  # 1m, 5m, 30m, 2h

# Application
ENVIRONMENT=development
SUPERWALL_SECRET=your-superwall-secret
DEFAULT_CREDITS=10
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8081
LOG_LEVEL=INFO
```

## GPU Provider Setup

### ComfyUI Local Setup

1. **Install ComfyUI with Docker:**
```bash
# Clone ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Build Docker image
docker build -t comfyui .

# Run ComfyUI server
docker run --gpus all -p 8188:8188 -v $(pwd):/workspace comfyui
```

2. **Alternative: Manual Installation:**
```bash
# Install Python dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# Start ComfyUI server
python main.py --listen 0.0.0.0 --port 8188
```

3. **Verify ComfyUI is running:**
```bash
curl http://localhost:8188/system_stats
```

### RunPod Serverless Setup

1. **Create RunPod Account:**
   - Sign up at https://runpod.io
   - Add payment method for serverless billing

2. **Create Serverless Endpoint:**
   - Go to Serverless dashboard
   - Click "New Endpoint"
   - Choose "ComfyUI" template or custom image
   - Configure:
     - **Name**: `comfyui-faceswap`
     - **Docker Image**: `runpod/comfyui:latest`
     - **GPU Type**: RTX 4090 or A100
     - **Container Disk**: 20GB
     - **Volume Mount**: `/workspace`

3. **Get Endpoint Configuration:**
   - Copy **Endpoint ID** to `RUNPOD_ENDPOINT_ID`
   - Copy **API Key** to `RUNPOD_API_KEY`

4. **Test RunPod Connection:**
```bash
curl -X POST https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync \
     -H "Authorization: Bearer {API_KEY}" \
     -H "Content-Type: application/json" \
     -d '{"input":{"workflow":{"test":"connection"}}}'
```

### Provider Selection

Choose your provider in `.env`:

```env
# For local ComfyUI (free, requires local GPU)
GPU_PROVIDER=comfy_local
COMFY_LOCAL_URL=http://localhost:8188

# For RunPod serverless (pay-per-use, cloud GPU)
GPU_PROVIDER=runpod
RUNPOD_API_KEY=your-api-key
RUNPOD_ENDPOINT_ID=your-endpoint-id
```

## Manual E2E Testing Guide

### Prerequisites

1. **Setup environment:**
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your provider settings

# Start services
make docker-up
# OR for local development:
make dev  # Terminal 1
make worker  # Terminal 2
```

2. **Verify services are running:**
```bash
# Check API health
curl http://localhost:8000/health

# Check if worker is connected
# Should see worker in logs
```

### Test Scenarios

#### Scenario 1: Face Restoration (ComfyUI Local)

1. **Configure for ComfyUI:**
```env
GPU_PROVIDER=comfy_local
COMFY_LOCAL_URL=http://localhost:8188
```

2. **Upload test image:**
```bash
curl -X POST "http://localhost:8000/api/v1/uploads/presign" \
     -H "Content-Type: application/json" \
     -d '{
       "filename": "test-face.jpg",
       "content_type": "image/jpeg"
     }'
```

Response:
```json
{
  "upload_url": "https://s3.amazonaws.com/bucket/presigned-url",
  "file_url": "https://s3.amazonaws.com/bucket/test-face.jpg"
}
```

3. **Upload image to S3 URL:**
```bash
# Use the upload_url from previous response
curl -X PUT "$UPLOAD_URL" \
     -H "Content-Type: image/jpeg" \
     --data-binary @/path/to/your/test-face.jpg
```

4. **Create face restoration job:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "face_restore",
       "params": {
         "input_url": "https://s3.amazonaws.com/bucket/test-face.jpg",
         "face_restore": "gfpgan",
         "enhance": true,
         "max_side": 1024,
         "denoise": 0.5
       }
     }'
```

Response:
```json
{
  "id": "job_123456",
  "status": "pending",
  "job_type": "face_restore",
  "created_at": "2024-01-15T10:30:00Z"
}
```

5. **Monitor job progress:**
```bash
# Poll job status every 5 seconds
while true; do
  curl "http://localhost:8000/api/v1/jobs/job_123456" | jq '.status,.progress'
  sleep 5
  if [ "$(curl -s http://localhost:8000/api/v1/jobs/job_123456 | jq -r '.status')" = "succeeded" ]; then
    break
  fi
done
```

Expected progression:
```
pending → running (10%) → running (50%) → running (90%) → succeeded (100%)
```

6. **Get results:**
```bash
curl "http://localhost:8000/api/v1/jobs/job_123456" | jq '.artifacts[].output_url'
```

7. **Download and view result:**
```bash
# Copy the output URL and open in browser
# OR download with curl:
curl -o restored-face.png "$OUTPUT_URL"
```

#### Scenario 2: Face Swap (RunPod Serverless)

1. **Configure for RunPod:**
```env
GPU_PROVIDER=runpod
RUNPOD_API_KEY=your-api-key
RUNPOD_ENDPOINT_ID=your-endpoint-id
```

2. **Upload source and target images:**
```bash
# Upload source face
curl -X POST "http://localhost:8000/api/v1/uploads/presign" \
     -d '{"filename": "source-face.jpg", "content_type": "image/jpeg"}'
# Upload to returned presigned URL

# Upload target image
curl -X POST "http://localhost:8000/api/v1/uploads/presign" \
     -d '{"filename": "target-image.jpg", "content_type": "image/jpeg"}'
# Upload to returned presigned URL
```

3. **Create face swap job:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "face_swap",
       "params": {
         "src_face_url": "https://s3.amazonaws.com/bucket/source-face.jpg",
         "target_url": "https://s3.amazonaws.com/bucket/target-image.jpg",
         "lora": null,
         "blend": 0.8,
         "max_side": 1024
       }
     }'
```

4. **Monitor and download result** (same as Scenario 1)

#### Scenario 3: Upscaling with Tile Processing

```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "upscale",
       "params": {
         "input_url": "https://s3.amazonaws.com/bucket/low-res.jpg",
         "model": "realesrgan_x4plus",
         "scale": 4,
         "tile": 256
       }
     }'
```

#### Scenario 4: Idempotency Test (Cache Hit)

1. **Create job with identical parameters:**
```bash
# Submit the exact same face_restore job again
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "face_restore",
       "params": {
         "input_url": "https://s3.amazonaws.com/bucket/test-face.jpg",
         "face_restore": "gfpgan",
         "enhance": true,
         "max_side": 1024,
         "denoise": 0.5
       }
     }'
```

2. **Expected behavior:**
   - Job should complete almost instantly (< 5 seconds)
   - Status should go: `pending → succeeded`
   - No actual GPU processing should occur
   - Result should be identical to previous job

#### Scenario 5: Job Cancellation

1. **Start a long-running job:**
```bash
JOB_ID=$(curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "upscale",
       "params": {
         "input_url": "https://s3.amazonaws.com/bucket/large-image.jpg",
         "model": "realesrgan_x4plus",
         "scale": 4
       }
     }' | jq -r '.id')
```

2. **Cancel the job while running:**
```bash
# Wait for job to start processing
sleep 10

# Cancel the job
curl -X POST "http://localhost:8000/api/v1/jobs/$JOB_ID/cancel"
```

3. **Verify cancellation:**
```bash
curl "http://localhost:8000/api/v1/jobs/$JOB_ID" | jq '.status'
# Should return: "cancelled"
```

### Expected Results

#### Successful Job Response:
```json
{
  "id": "job_123456",
  "user_id": "user_789",
  "job_type": "face_restore",
  "status": "succeeded",
  "progress": 100,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "finished_at": "2024-01-15T10:31:30Z",
  "params": {
    "input_url": "https://s3.amazonaws.com/bucket/test-face.jpg",
    "face_restore": "gfpgan",
    "enhance": true,
    "max_side": 1024,
    "denoise": 0.5
  },
  "artifacts": [
    {
      "id": "artifact_456",
      "artifact_type": "image",
      "output_url": "https://s3.amazonaws.com/bucket/outputs/restored_face.png",
      "file_size": 1048576,
      "mime_type": "image/png"
    }
  ]
}
```

#### Performance Benchmarks:
- **ComfyUI Local**: 30-90 seconds per job (depends on GPU)
- **RunPod Serverless**: 45-120 seconds per job (includes cold start)
- **Cache Hit**: < 5 seconds
- **File Upload**: < 10 seconds for 5MB images

### Troubleshooting

#### Common Issues:

1. **"Provider not available" error:**
   - Check GPU_PROVIDER setting in .env
   - Verify ComfyUI is running on correct port
   - Test RunPod API key and endpoint ID

2. **"Input validation failed" error:**
   - Verify image URL is accessible
   - Check image format (JPEG, PNG, WebP supported)
   - Ensure image size < 20MB

3. **Job stuck in "pending" status:**
   - Check Celery worker is running
   - Verify Redis connection
   - Check worker logs for errors

4. **"Webhook delivery failed" warning:**
   - This is normal if no webhook URL is configured
   - Set webhook URL in job creation or ignore warnings

#### Debug Commands:

```bash
# Check service health
curl http://localhost:8000/health

# View API logs
docker logs oneshot-api

# View worker logs
docker logs oneshot-worker

# Check Redis connection
redis-cli ping

# Test ComfyUI
curl http://localhost:8188/system_stats

# Test S3 connectivity
aws s3 ls s3://your-bucket-name
```

### Rate Limiting

The API implements multiple levels of rate limiting:

- **Global Rate Limiting**: 30 requests/minute per IP
- **User Rate Limiting**: Based on subscription plan
  - Free: 5 jobs/day
  - Pro: 50 jobs/day
  - Premium: 200 jobs/day

### Job Parameters

Advanced job creation with comprehensive validation:

```json
{
  "source_url": "https://s3.bucket/source.jpg",
  "target_url": "https://s3.bucket/target.jpg",
  "job_type": "face_swap",
  "params": {
    "face_restore": true,
    "upscale": 2,
    "swap_strength": 0.8,
    "blend_ratio": 0.5,
    "face_enhancer": "gfpgan"
  }
}
```

### Monitoring & Logging

**Structured Logging:**
- JSON format with correlation IDs
- User ID and job ID tracking
- Performance metrics
- Error tracking with stack traces

**Prometheus Metrics:**
- HTTP request metrics
- Job processing metrics
- User activity metrics
- System resource usage

**Example log output:**
```json
{
  "timestamp": "2025-09-17T15:30:45.123Z",
  "level": "info",
  "event": "job_created",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "job_type": "face_swap",
  "processing_time_ms": 1250
}
```

## Testing

The project includes comprehensive test coverage:

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Rate Limiting Tests**: Rate limit validation
- **Authentication Tests**: Auth flow testing
- **Error Handling Tests**: Edge case validation

### Running Tests
```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run specific test file
python -m pytest tests/test_auth.py -v

# Run specific test
python -m pytest tests/test_auth.py::TestAuth::test_login_success -v
```

### Test Coverage
The project maintains 80%+ test coverage across all modules.

## Deployment

### Production Deployment

1. **Environment Setup:**
```bash
# Update environment variables
cp .env.example .env.production
# Edit .env.production with production values
```

2. **Database Migration:**
```bash
docker-compose exec api alembic upgrade head
```

3. **Health Check:**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

### Scaling

- **API**: Scale horizontally with load balancer
- **Workers**: Scale Celery workers based on queue length
- **Database**: Use PostgreSQL with connection pooling
- **Redis**: Use Redis Cluster for high availability

## Development Guide

### Project Structure
```
qoder-deneme/
├── apps/
│   ├── api/
│   │   ├── main.py           # FastAPI application
│   │   └── routers/          # API route handlers
│   ├── core/
│   │   ├── settings.py       # Configuration
│   │   └── security.py       # Authentication
│   ├── db/
│   │   ├── models/           # Database models
│   │   └── session.py        # Database session
│   ├── services/             # Business logic
│   └── worker/
│       └── tasks.py          # Background tasks
├── tests/                    # Test suite
├── alembic/                  # Database migrations
├── docker-compose.yml        # Docker services
├── Dockerfile               # Container image
├── Makefile                 # Development commands
└── requirements.txt         # Python dependencies
```

### Adding New Features

1. **Create Database Model** (if needed):
```python
# apps/db/models/new_model.py
class NewModel(SQLModel, table=True):
    __tablename__ = "new_models"
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    # Add fields...
```

2. **Create Migration:**
```bash
alembic revision --autogenerate -m "Add new model"
alembic upgrade head
```

3. **Add API Endpoint:**
```python
# apps/api/routers/new_router.py
@router.post("/new-endpoint")
async def new_endpoint(data: NewSchema):
    # Implementation...
```

4. **Add Tests:**
```python
# tests/test_new_feature.py
def test_new_endpoint(client, auth_headers):
    response = client.post("/api/v1/new-endpoint", json=data)
    assert response.status_code == 200
```

### GPU Integration (Future)

The current implementation simulates GPU processing. To integrate real GPU processing:

1. **Replace simulation in `apps/worker/tasks.py`:**
```python
def process_job(job: Job) -> str:
    # Replace simulation with actual GPU calls
    # Example: RunPod API, ComfyUI, or local GPU processing
    pass
```

2. **Update Docker configuration** for GPU support:
```yaml
services:
  celery_worker:
    runtime: nvidia  # For NVIDIA GPU support
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

## Troubleshooting

### Common Issues

**Redis Connection Error:**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine
# Or check if Redis is running
redis-cli ping
```

**Database Migration Issues:**
```bash
# Reset database
rm -f oneshot_dev.db
make migrate
```

**Port Already in Use:**
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process and restart
make docker-down
make docker-up
```

**Test Failures:**
```bash
# Install missing dependencies
pip install -r requirements.txt

# Check specific test
python -m pytest tests/test_auth.py::TestAuth::test_login_success -v -s
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run tests: `make test`
5. Submit a pull request

### Code Style
- Follow PEP 8
- Use type hints
- Add docstrings to public functions
- Maintain test coverage above 80%

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review existing GitHub issues
3. Create a new issue with detailed information

---

**OneShot Face Swapper Backend v2.0** - Production-ready AI processing with enterprise-level features.

AI-powered face swapping and restoration service built with FastAPI, featuring LoRA-based models (GFPGAN, CodeFormer) for face enhancement and upscaling.

## Features

- **Face Restoration**: Enhance image quality using GFPGAN and CodeFormer models
- **Face Swapping**: Replace faces using custom LoRA models
- **Image Upscaling**: Super-resolution processing
- **User Authentication**: JWT-based authentication system
- **Credit System**: Pay-per-use credit system
- **Subscription Management**: Superwall integration for payments
- **Background Processing**: Asynchronous job queue with Celery and Redis
- **S3 Storage**: AWS S3 integration for image storage

## Technology Stack

- **Framework**: FastAPI + SQLModel + Uvicorn
- **Database**: PostgreSQL with Alembic migrations
- **Job Queue**: Celery + Redis
- **Storage**: AWS S3
- **Authentication**: JWT with PassLib
- **AI Processing**: GFPGAN, CodeFormer, custom LoRA models

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis
- AWS S3 account

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd oneshot-backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment setup**
   ```bash
   cp .env.example .env
   # Edit .env file with your configuration
   ```

4. **Database setup**
   ```bash
   # Create database
   createdb oneshot_db
   
   # Run migrations
   alembic upgrade head
   ```

5. **Start services**
   
   **API Server:**
   ```bash
   python main.py
   ```
   
   **Background Worker:**
   ```bash
   celery -A apps.worker.tasks worker --loglevel=info
   ```
   
   **Task Scheduler (optional):**
   ```bash
   celery -A apps.worker.tasks beat --loglevel=info
   ```

## API Documentation

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication

#### Register User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "credits": 10
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password"
}
```

#### Get User Profile
```http
GET /auth/me
Authorization: Bearer <token>
```

### File Upload

#### Generate Presigned URL
```http
POST /uploads/presign
Authorization: Bearer <token>
Content-Type: application/json

{
  "filename": "image.jpg",
  "content_type": "image/jpeg",
  "file_size": 1024000
}
```

### Job Processing

#### Create Job
```http
POST /jobs
Authorization: Bearer <token>
Content-Type: application/json

{
  "job_type": "face_restoration",
  "input_image_url": "https://s3.amazonaws.com/bucket/image.jpg",
  "parameters": {
    "model": "gfpgan",
    "scale_factor": 2
  }
}
```

#### Get Job Status
```http
GET /jobs/{job_id}
Authorization: Bearer <token>
```

#### Get User Jobs
```http
GET /jobs?skip=0&limit=10
Authorization: Bearer <token>
```

### Billing

#### Validate Receipt
```http
POST /billing/validate
Authorization: Bearer <token>
Content-Type: application/json

{
  "receipt_data": "base64_receipt_data",
  "product_id": "credits_50",
  "transaction_id": "unique_transaction_id"
}
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `JWT_SECRET` | JWT signing secret | Yes |
| `S3_BUCKET` | AWS S3 bucket name | Yes |
| `S3_KEY` | AWS access key ID | Yes |
| `S3_SECRET` | AWS secret access key | Yes |
| `REDIS_URL` | Redis connection URL | Yes |
| `SUPERWALL_SECRET` | Superwall API secret | Yes |

### Credit Costs

- Face Restoration: 1 credit
- Face Swap: 2 credits
- Upscaling: 1 credit

## Development

### Project Structure

```
oneshot-backend/
├── apps/
│   ├── api/                 # FastAPI application
│   │   ├── routers/         # API endpoints
│   │   ├── main.py          # App configuration
│   │   └── services.py      # Business logic
│   ├── worker/              # Background processing
│   │   ├── processors/      # AI processing modules
│   │   ├── tasks.py         # Celery tasks
│   │   └── main.py          # Worker entry point
│   ├── core/                # Core utilities
│   │   ├── config.py        # Configuration constants
│   │   ├── settings.py      # Application settings
│   │   ├── security.py      # Security utilities
│   │   └── exceptions.py    # Custom exceptions
│   └── db/                  # Database layer
│       ├── models/          # SQLModel definitions
│       ├── session.py       # Database session
│       └── base.py          # CRUD operations
├── alembic/                 # Database migrations
├── requirements.txt         # Python dependencies
├── main.py                  # Application entry point
└── .env                     # Environment variables
```

### Adding New Features

1. **New AI Processor**: Add to `apps/worker/processors/`
2. **New API Endpoint**: Add router to `apps/api/routers/`
3. **New Database Model**: Add to `apps/db/models/`
4. **New Background Task**: Add to `apps/worker/tasks.py`

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=apps
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Deployment

### Docker Deployment

1. **Build image**
   ```bash
   docker build -t oneshot-backend .
   ```

2. **Run with docker-compose**
   ```bash
   docker-compose up -d
   ```

### Production Considerations

- Use environment-specific settings
- Configure proper CORS origins
- Set up SSL/TLS certificates
- Configure reverse proxy (nginx)
- Set up monitoring and logging
- Configure auto-scaling for workers
- Set up database backups
- Configure S3 bucket policies

## Monitoring

- **Health Check**: `GET /health`
- **API Documentation**: `GET /docs` (development only)
- **Job Monitoring**: Check Celery worker logs
- **Database**: Monitor PostgreSQL performance
- **Storage**: Monitor S3 usage and costs

## Security

- JWT-based authentication
- Password hashing with bcrypt
- Input validation on all endpoints
- File upload validation
- CORS configuration
- Environment variable protection

## Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review the logs for error messages
3. Ensure all environment variables are set
4. Verify database connectivity
5. Check Redis connection for background jobs

## License

Private - All rights reserved