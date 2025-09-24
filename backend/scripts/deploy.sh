#!/bin/bash

set -euo pipefail

# Deployment script for OneShot Face Swapper
# Usage: ./scripts/deploy.sh [staging|production]

ENVIRONMENT=${1:-staging}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_ROOT/deploy/$ENVIRONMENT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    error "Invalid environment. Use 'staging' or 'production'"
fi

log "Starting deployment to $ENVIRONMENT environment..."

# Check prerequisites
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not in PATH"
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed or not in PATH"
fi

# Navigate to deployment directory
cd "$DEPLOY_DIR" || error "Deployment directory not found: $DEPLOY_DIR"

# Check for environment file
if [[ ! -f ".env" ]]; then
    error "Environment file not found. Copy .env.example to .env and configure it."
fi

# Source environment variables
source .env

# Generate deployment ID
DEPLOYMENT_ID="${GITHUB_SHA:-$(date +%s)}-$(date +%s)"
export DEPLOYMENT_ID

log "Deployment ID: $DEPLOYMENT_ID"

# Create backup of current deployment
log "Creating backup of current deployment..."
BACKUP_DIR="$PROJECT_ROOT/backups/$ENVIRONMENT"
mkdir -p "$BACKUP_DIR"

if docker-compose ps | grep -q "Up"; then
    docker-compose config > "$BACKUP_DIR/docker-compose-backup-$DEPLOYMENT_ID.yml"
    success "Backup created: $BACKUP_DIR/docker-compose-backup-$DEPLOYMENT_ID.yml"
fi

# Create networks if they don't exist
log "Setting up Docker networks..."
docker network create web 2>/dev/null || true
docker network create internal 2>/dev/null || true

# Create acme.json file for Let's Encrypt
if [[ ! -f "acme.json" ]]; then
    log "Creating acme.json for Let's Encrypt..."
    touch acme.json
    chmod 600 acme.json
fi

# Pull latest images
log "Pulling latest Docker images..."
docker-compose pull

# Run database migrations
log "Running database migrations..."
docker-compose run --rm app python -m alembic upgrade head || error "Migration failed"

# Health check function
health_check() {
    local service_name=$1
    local health_url=$2
    local max_attempts=30
    local attempt=1

    log "Performing health check for $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            success "$service_name is healthy"
            return 0
        fi
        
        log "Health check attempt $attempt/$max_attempts for $service_name..."
        sleep 10
        ((attempt++))
    done
    
    error "$service_name failed health check after $max_attempts attempts"
}

# Deploy with zero-downtime strategy
log "Starting zero-downtime deployment..."

# Start new services
docker-compose up -d

# Wait for services to be ready
sleep 20

# Health checks
health_check "Application" "http://localhost:8000/healthz"
health_check "Readiness" "http://localhost:8000/readyz"

# Verify metrics endpoint
log "Checking metrics endpoint..."
if curl -f -s "http://localhost:8000/metrics" > /dev/null; then
    success "Metrics endpoint is accessible"
else
    warning "Metrics endpoint is not accessible"
fi

# Test API endpoints
log "Testing critical API endpoints..."
curl -f -s "http://localhost:8000/docs" > /dev/null && success "API docs accessible" || warning "API docs not accessible"

# Run post-deployment hooks
if [[ -f "$PROJECT_ROOT/scripts/post-deploy-hooks.sh" ]]; then
    log "Running post-deployment hooks..."
    bash "$PROJECT_ROOT/scripts/post-deploy-hooks.sh" "$ENVIRONMENT"
fi

# Clean up old images and containers
log "Cleaning up old Docker resources..."
docker system prune -f --volumes

success "Deployment to $ENVIRONMENT completed successfully!"
log "Deployment ID: $DEPLOYMENT_ID"
log "Services status:"
docker-compose ps

# Save deployment info
echo "$DEPLOYMENT_ID" > "$PROJECT_ROOT/.last-deployment-$ENVIRONMENT"
echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')" > "$PROJECT_ROOT/.last-deployment-time-$ENVIRONMENT"

log "Deployment information saved. Use 'make rollback:$ENVIRONMENT' if needed."