# Supabase Migration Implementation Guide

This document provides a complete implementation guide for migrating the FastAPI backend from SQLModel/SQLite to Supabase.

## Migration Overview

The migration has been successfully implemented with the following key changes:

### ✅ Phase 1: Environment Setup
- ✅ Updated `requirements.txt` with Supabase dependencies
- ✅ Created Supabase client wrapper (`apps/core/supabase_client.py`)
- ✅ Implemented JWT validation using Supabase secret
- ✅ Updated settings to include Supabase configuration

### ✅ Phase 2: Database Migration
- ✅ Created database schema SQL files (`supabase/schema.sql`)
- ✅ Implemented Row Level Security policies (`supabase/rls_policies.sql`)
- ✅ Created atomic credit operation RPC functions (`supabase/functions.sql`)
- ✅ Set up storage buckets and policies (`supabase/storage.sql`)

### ✅ Phase 3: Service Layer Refactoring
- ✅ Replaced SQLModel operations with PostgREST calls in `services.py`
- ✅ Implemented stateless service methods
- ✅ Updated error handling for API responses

### ✅ Phase 4: Authentication Migration
- ✅ Removed custom JWT endpoints (registration/login handled by Supabase)
- ✅ Implemented Supabase JWT validation middleware
- ✅ Added profile bootstrap endpoint for new users
- ✅ Updated all routers to use `SupabaseUser` authentication

### ✅ Phase 5: Storage Migration
- ✅ Replaced S3 with Supabase Storage
- ✅ Implemented client-direct upload instructions
- ✅ Updated file access patterns with RLS enforcement

### 📋 Phase 6: Testing & Validation (Next Steps)
- 🔄 Update existing tests to work with Supabase backend
- 🔄 Validate RLS policy effectiveness
- 🔄 Test authentication flow end-to-end

## Implementation Files

### Core Infrastructure
- `apps/core/supabase_client.py` - Supabase client wrapper
- `apps/core/security.py` - JWT validation and auth dependencies
- `apps/core/settings.py` - Updated configuration
- `apps/api/services.py` - Refactored service layer

### API Routers
- `apps/api/routers/auth.py` - Profile management (no auth endpoints)
- `apps/api/routers/jobs.py` - Job creation and management
- `apps/api/routers/uploads.py` - Supabase Storage upload instructions
- `apps/api/routers/credits.py` - Credit transaction management

### Database Schema
- `supabase/schema.sql` - Complete database schema
- `supabase/rls_policies.sql` - Row Level Security policies
- `supabase/functions.sql` - Atomic RPC functions
- `supabase/storage.sql` - Storage bucket configuration
- `supabase/setup.sql` - Complete setup script

### Configuration
- `.env.supabase` - Environment template
- `requirements.txt` - Updated dependencies

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Supabase Project
1. Create a new Supabase project
2. Copy the configuration values to your `.env` file using `.env.supabase` as template
3. Run the database setup scripts in Supabase SQL Editor:
   ```sql
   -- Run these in order:
   -- 1. schema.sql
   -- 2. rls_policies.sql  
   -- 3. functions.sql
   -- 4. storage.sql
   ```

### 3. Environment Variables
Set the following required environment variables:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

### 4. Start the Application
```bash
uvicorn apps.api.main:app --reload
```

## API Changes

### Authentication Flow
**Before (Custom JWT):**
```
POST /api/auth/register
POST /api/auth/login
GET /api/auth/me
```

**After (Supabase Auth):**
```
# Authentication handled by Supabase client-side
POST /api/bootstrap-profile  # Initialize profile after Supabase auth
GET /api/profile             # Get profile with transactions
```

### New Endpoints
```
# Jobs
POST /api/jobs               # Create job
GET /api/jobs                # List user jobs
GET /api/jobs/{job_id}       # Get job status

# Uploads (Supabase Storage)
POST /api/uploads/instructions     # Get upload instructions
GET /api/uploads/download/{path}   # Get download URL

# Credits
GET /api/credits              # Get transactions
GET /api/credits/balance      # Get current balance
```

## Key Architectural Changes

### 1. Authentication
- **Before**: Custom JWT with database user lookup
- **After**: Supabase JWT validation with stateless user context

### 2. Data Access
- **Before**: SQLModel ORM with sessions
- **After**: PostgREST API calls with Row Level Security

### 3. File Storage
- **Before**: Server-side S3 uploads with presigned URLs
- **After**: Client-direct Supabase Storage with auth tokens

### 4. Credit System
- **Before**: Database transactions with potential race conditions
- **After**: Atomic RPC functions preventing race conditions

## Security Enhancements

### Row Level Security
- All tables enforce user-level data isolation
- Service role can override for system operations
- No way for users to access other users' data

### JWT Validation
- Tokens validated against Supabase shared secret
- User context extracted directly from token claims
- No database lookups required for authentication

### Storage Security
- Path-based access control (user_id prefix required)
- Signed URLs for temporary access
- Automatic policy enforcement

## Benefits of Migration

1. **Scalability**: PostgREST scales better than ORM
2. **Security**: RLS provides database-level security
3. **Performance**: Stateless authentication, atomic operations
4. **Maintainability**: Less custom auth code to maintain
5. **Features**: Built-in real-time subscriptions, storage, auth

## Client-Side Integration

The client applications need to be updated to:

1. **Use Supabase Auth** instead of custom registration/login endpoints
2. **Call bootstrap-profile** after successful authentication
3. **Upload directly to Supabase Storage** using provided instructions
4. **Include JWT token** in all API requests

## Migration Checklist

- [x] Update backend dependencies
- [x] Implement Supabase client wrapper
- [x] Create database schema and policies
- [x] Refactor service layer
- [x] Update authentication system
- [x] Migrate storage to Supabase
- [x] Update API routers
- [x] Create configuration templates
- [ ] Update tests
- [ ] Update client applications
- [ ] Deploy and validate

## Next Steps

1. **Test the Implementation**: Validate all endpoints work correctly
2. **Update Client Apps**: Modify frontend to use Supabase Auth
3. **Migration Testing**: Test with real data migration
4. **Performance Testing**: Validate performance improvements
5. **Documentation**: Update API documentation

The migration implementation is complete and ready for testing and deployment.