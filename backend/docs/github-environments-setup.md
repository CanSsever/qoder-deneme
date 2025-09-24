# GitHub Environments Setup Guide

This document explains how to configure GitHub Environments for secure deployment with secrets management.

## Creating GitHub Environments

### 1. Navigate to Repository Settings
1. Go to your repository on GitHub
2. Click on "Settings" tab
3. In the left sidebar, click "Environments"

### 2. Create Staging Environment
1. Click "New environment"
2. Name: `staging`
3. Configure the following settings:

#### Environment Protection Rules
- **Required reviewers**: Optional (recommended for production)
- **Wait timer**: 0 minutes for staging
- **Deployment branches**: Limit to `develop` branch only

#### Environment Secrets
Add the following secrets (click "Add secret" for each):

```
# Database Configuration
DATABASE_URL=postgresql://username:password@your-neon-db-host:5432/staging_db

# JWT Configuration  
JWT_SECRET_KEY=your-staging-jwt-secret-key-here

# AWS/Cloudflare R2 Storage
AWS_ACCESS_KEY_ID=your-r2-access-key
AWS_SECRET_ACCESS_KEY=your-r2-secret-key
AWS_REGION=auto
S3_BUCKET_NAME=oneshot-staging-bucket
S3_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com

# Payment Configuration
SUPERWALL_SIGNING_SECRET=your-staging-superwall-secret
ENTITLEMENTS_DEFAULT_PLAN=free
DEV_BILLING_MODE=true

# AI Provider Keys
RUNPOD_API_KEY=your-runpod-api-key
COMFYUI_BASE_URL=https://your-comfyui-staging-endpoint.com

# Domain Configuration
STAGING_URL=https://staging.yourdomain.com
DOMAIN=staging.yourdomain.com
ACME_EMAIL=admin@yourdomain.com

# Cloudflare Configuration (for SSL)
CLOUDFLARE_EMAIL=admin@yourdomain.com
CLOUDFLARE_API_KEY=your-cloudflare-global-api-key

# Registry Configuration
REGISTRY=ghcr.io
IMAGE_NAME=your-org/oneshot-face-swapper

# Monitoring
SENTRY_DSN=https://your-staging-sentry-dsn@sentry.io/project-id
```

#### Environment Variables (Non-Secret)
Add these as environment variables (not secrets):

```
ENVIRONMENT=staging
LOG_LEVEL=INFO
WORKERS_COUNT=2
```

### 3. Create Production Environment
1. Click "New environment"
2. Name: `production`
3. Configure the following settings:

#### Environment Protection Rules
- **Required reviewers**: Add at least 1-2 reviewers
- **Wait timer**: 5-10 minutes (gives time to cancel if needed)
- **Deployment branches**: Limit to `main` branch only

#### Environment Secrets
Add the same secrets as staging but with production values:

```
# Database Configuration
DATABASE_URL=postgresql://username:password@your-production-db-host:5432/production_db

# JWT Configuration (DIFFERENT from staging)
JWT_SECRET_KEY=your-production-jwt-secret-key-here

# AWS/Cloudflare R2 Storage (Production bucket)
AWS_ACCESS_KEY_ID=your-production-r2-access-key
AWS_SECRET_ACCESS_KEY=your-production-r2-secret-key
S3_BUCKET_NAME=oneshot-production-bucket

# Payment Configuration (Production keys)
SUPERWALL_SIGNING_SECRET=your-production-superwall-secret
ENTITLEMENTS_DEFAULT_PLAN=free
DEV_BILLING_MODE=false

# AI Provider Keys (Production)
RUNPOD_API_KEY=your-production-runpod-api-key
COMFYUI_BASE_URL=https://your-comfyui-production-endpoint.com

# Domain Configuration
PRODUCTION_URL=https://api.yourdomain.com
DOMAIN=api.yourdomain.com

# Monitoring (Production)
SENTRY_DSN=https://your-production-sentry-dsn@sentry.io/project-id
```

## Security Best Practices

### 1. Secret Naming Convention
- Use UPPER_CASE for secret names
- Prefix environment-specific secrets with env name if needed
- Never include the actual values in code or docs

### 2. Secret Rotation
- Rotate secrets regularly (quarterly recommended)
- Update both GitHub secrets and external services
- Test deployments after rotation

### 3. Access Control
- Limit repository access to necessary team members
- Use required reviewers for production deployments
- Enable branch protection rules

### 4. Masked Variables
The following variables should be masked in logs:
- `JWT_SECRET_KEY`
- `AWS_SECRET_ACCESS_KEY`
- `SUPERWALL_SIGNING_SECRET`
- `RUNPOD_API_KEY`
- `CLOUDFLARE_API_KEY`
- `DATABASE_URL` (contains password)

GitHub automatically masks these in workflow logs when stored as secrets.

## Verification Steps

After setting up environments:

1. **Test Staging Deployment**:
   ```bash
   # Push to develop branch to trigger staging deployment
   git checkout develop
   git push origin develop
   ```

2. **Test Production Deployment**:
   ```bash
   # Create PR to main branch
   git checkout main
   git pull origin main
   git merge develop
   git push origin main
   ```

3. **Verify Secrets**:
   - Check workflow logs to ensure no secrets are exposed
   - Verify masked variables appear as `***` in logs
   - Test application functionality with each environment

## Troubleshooting

### Common Issues

1. **Secret Not Found**:
   - Verify secret name matches exactly in workflow
   - Check environment name is correct
   - Ensure secret is added to correct environment

2. **Deployment Branch Restriction**:
   - Staging should allow `develop` branch
   - Production should allow `main` branch only
   - Check branch protection rules

3. **Required Reviewers**:
   - Add team members as repository collaborators
   - Assign reviewers in environment settings
   - Test review process with test deployment

### Validation Commands

```bash
# Test secret access in workflow
echo "Testing secret access..."
echo "Database URL configured: $(if [ -n "$DATABASE_URL" ]; then echo "Yes"; else echo "No"; fi)"
echo "JWT Secret configured: $(if [ -n "$JWT_SECRET_KEY" ]; then echo "Yes"; else echo "No"; fi)"

# Test environment detection
echo "Environment: $GITHUB_ENVIRONMENT"
echo "Branch: $GITHUB_REF_NAME"
```

## Next Steps

After configuring GitHub Environments:

1. Test deployments to both environments
2. Set up monitoring and alerting
3. Configure backup and disaster recovery
4. Document incident response procedures
5. Train team on deployment process