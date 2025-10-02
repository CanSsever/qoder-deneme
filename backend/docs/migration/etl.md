# SQLite → Postgres ETL Migration Guide

This document describes the strategy for safely migrating data from the legacy SQLite database to Supabase Postgres.

## Overview

The ETL (Extract, Transform, Load) process involves migrating non-authentication data from SQLite to Postgres while handling ID mapping and ensuring data integrity.

## Critical Considerations

### What NOT to Migrate
- **User authentication data** (passwords, tokens) - handled by Supabase Auth
- **User profiles** - created automatically on first login via bootstrap process
- **Legacy user IDs** - Supabase generates new UUIDs for users

### What TO Migrate
- **Job records** - processing history and artifacts
- **Credit transactions** - billing and usage history
- **Non-auth metadata** - application-specific data

## Migration Strategy

### Phase 1: Data Export
Export relevant data from SQLite to CSV format with explicit typing and validation.

### Phase 2: Data Transformation
- Convert legacy user IDs to email-based lookups
- Generate new UUIDs where needed
- Transform dates to ISO 8601 format
- Validate foreign key relationships

### Phase 3: Data Loading
- Create staging tables in Postgres
- Validate data integrity
- Insert into production tables with proper FK relationships
- Create user mapping tables for legacy ID references

## Implementation Steps

### 1. Identify Tables to Migrate

Common tables that typically need migration:
```sql
-- Jobs table (processing history)
SELECT id, user_id, job_type, status, created_at, updated_at, 
       source_file, result_file, metadata
FROM jobs;

-- Credit transactions (billing history)
SELECT id, user_id, amount, transaction_type, reference_id, 
       created_at, description
FROM credit_transactions;

-- Any custom application data
SELECT * FROM custom_data_table;
```

### 2. Export Data with Proper Typing

```bash
# Export jobs data
sqlite3 legacy_database.db <<EOF
.headers on
.mode csv
.output data/export_jobs.csv
SELECT 
    id,
    user_id,
    job_type,
    status,
    datetime(created_at, 'localtime') as created_at,
    datetime(updated_at, 'localtime') as updated_at,
    source_file,
    result_file,
    metadata
FROM jobs
ORDER BY created_at;
.quit
EOF

# Export credit transactions
sqlite3 legacy_database.db <<EOF
.headers on
.mode csv
.output data/export_credit_transactions.csv
SELECT 
    id,
    user_id,
    amount,
    transaction_type,
    reference_id,
    datetime(created_at, 'localtime') as created_at,
    description
FROM credit_transactions
ORDER BY created_at;
.quit
EOF

# Export user email mapping (for ID resolution)
sqlite3 legacy_database.db <<EOF
.headers on
.mode csv
.output data/export_user_mapping.csv
SELECT 
    id as legacy_user_id,
    email,
    datetime(created_at, 'localtime') as created_at
FROM users
WHERE email IS NOT NULL;
.quit
EOF
```

### 3. Create Staging Tables in Postgres

Run these commands in your Supabase SQL Editor:

```sql
-- Staging table for jobs
CREATE TABLE IF NOT EXISTS stg_jobs (
    legacy_id TEXT,
    legacy_user_id TEXT,
    user_email TEXT,
    job_type TEXT,
    status TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source_file TEXT,
    result_file TEXT,
    metadata JSONB,
    -- Helper fields for transformation
    supabase_user_id UUID,
    new_job_id UUID DEFAULT gen_random_uuid()
);

-- Staging table for credit transactions
CREATE TABLE IF NOT EXISTS stg_credit_transactions (
    legacy_id TEXT,
    legacy_user_id TEXT,
    user_email TEXT,
    amount INTEGER,
    transaction_type TEXT,
    reference_id TEXT,
    created_at TIMESTAMPTZ,
    description TEXT,
    -- Helper fields for transformation
    supabase_user_id UUID,
    new_transaction_id UUID DEFAULT gen_random_uuid()
);

-- User mapping table (persistent)
CREATE TABLE IF NOT EXISTS legacy_user_map (
    legacy_user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    supabase_user_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    migrated_at TIMESTAMPTZ
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_legacy_user_map_email ON legacy_user_map(email);
CREATE INDEX IF NOT EXISTS idx_stg_jobs_email ON stg_jobs(user_email);
CREATE INDEX IF NOT EXISTS idx_stg_credit_transactions_email ON stg_credit_transactions(user_email);
```

### 4. Data Transformation Process

The transformation involves several steps:

1. **Load CSV data into staging tables**
2. **Resolve user IDs via email lookup**
3. **Validate data integrity**
4. **Transform to final format**

```sql
-- After loading CSV data, resolve user IDs
-- This should be done after users have migrated and logged in at least once

-- Update staging tables with Supabase user IDs
UPDATE stg_jobs 
SET supabase_user_id = (
    SELECT p.id 
    FROM profiles p 
    WHERE p.email = stg_jobs.user_email
)
WHERE user_email IS NOT NULL;

UPDATE stg_credit_transactions 
SET supabase_user_id = (
    SELECT p.id 
    FROM profiles p 
    WHERE p.email = stg_credit_transactions.user_email
)
WHERE user_email IS NOT NULL;

-- Update legacy user mapping
UPDATE legacy_user_map 
SET supabase_user_id = (
    SELECT p.id 
    FROM profiles p 
    WHERE p.email = legacy_user_map.email
)
WHERE email IS NOT NULL;
```

### 5. Data Validation

Before loading into production tables, validate the data:

```sql
-- Check for unmapped users
SELECT COUNT(*) as unmapped_jobs 
FROM stg_jobs 
WHERE supabase_user_id IS NULL;

SELECT COUNT(*) as unmapped_transactions 
FROM stg_credit_transactions 
WHERE supabase_user_id IS NULL;

-- Check data integrity
SELECT 
    COUNT(*) as total_jobs,
    COUNT(DISTINCT supabase_user_id) as unique_users,
    MIN(created_at) as earliest_job,
    MAX(created_at) as latest_job
FROM stg_jobs 
WHERE supabase_user_id IS NOT NULL;

-- Check for duplicate references
SELECT reference_id, COUNT(*) 
FROM stg_credit_transactions 
WHERE reference_id IS NOT NULL 
GROUP BY reference_id 
HAVING COUNT(*) > 1;
```

### 6. Load into Production Tables

Once validation passes, load data into production tables:

```sql
-- Load jobs (only for users who have been mapped)
INSERT INTO jobs (
    id, user_id, job_type, status, created_at, updated_at,
    source_file, result_file, metadata
)
SELECT 
    new_job_id,
    supabase_user_id,
    job_type,
    status,
    created_at,
    updated_at,
    source_file,
    result_file,
    metadata::jsonb
FROM stg_jobs 
WHERE supabase_user_id IS NOT NULL
ON CONFLICT (id) DO NOTHING;  -- Prevent duplicates

-- Load credit transactions
INSERT INTO credit_transactions (
    id, user_id, amount, transaction_type, reference_id,
    created_at, description
)
SELECT 
    new_transaction_id,
    supabase_user_id,
    amount,
    transaction_type,
    reference_id,
    created_at,
    description
FROM stg_credit_transactions 
WHERE supabase_user_id IS NOT NULL
ON CONFLICT (id) DO NOTHING;  -- Prevent duplicates

-- Update legacy mapping with migration timestamp
UPDATE legacy_user_map 
SET migrated_at = NOW() 
WHERE supabase_user_id IS NOT NULL 
AND migrated_at IS NULL;
```

## Post-Migration Tasks

### 1. Verification Queries

Run these queries to verify successful migration:

```sql
-- Compare record counts
SELECT 'Original Jobs' as source, COUNT(*) as count FROM stg_jobs
UNION ALL
SELECT 'Migrated Jobs' as source, COUNT(*) as count FROM jobs
UNION ALL
SELECT 'Original Transactions' as source, COUNT(*) as count FROM stg_credit_transactions
UNION ALL
SELECT 'Migrated Transactions' as source, COUNT(*) as count FROM credit_transactions;

-- Check user distribution
SELECT 
    u.email,
    COUNT(j.id) as job_count,
    COUNT(ct.id) as transaction_count,
    SUM(ct.amount) as total_credits
FROM profiles u
LEFT JOIN jobs j ON j.user_id = u.id
LEFT JOIN credit_transactions ct ON ct.user_id = u.id
GROUP BY u.id, u.email
ORDER BY job_count DESC
LIMIT 10;

-- Check data integrity
SELECT 
    COUNT(*) as total_jobs,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '1 year') as old_jobs
FROM jobs;
```

### 2. Cleanup

After successful migration and verification:

```sql
-- Drop staging tables (optional, keep for audit trail)
-- DROP TABLE IF EXISTS stg_jobs;
-- DROP TABLE IF EXISTS stg_credit_transactions;

-- Keep legacy_user_map for future reference
-- This table helps resolve any legacy ID references
```

## ETL Script Template

The `tools/etl_example.py` script provides a guided template for the ETL process. It demonstrates:

- Reading from SQLite database
- Exporting to CSV with proper formatting
- Creating staging tables
- Basic data transformation patterns
- Validation checks

## Timeline and Dependencies

### Pre-Migration Requirements
- [ ] User migration completed (users have logged in at least once)
- [ ] Profile bootstrap process working correctly
- [ ] Staging environment tested with sample data

### Migration Process (Recommended Order)
1. **Export data from SQLite** (can be done anytime)
2. **Wait for user migration completion** (critical dependency)
3. **Create staging tables in Postgres**
4. **Load and transform data**
5. **Validate data integrity**
6. **Load into production tables**
7. **Verify and cleanup**

### Estimated Timeline
- Small dataset (<10k records): 1-2 hours
- Medium dataset (10k-100k records): 4-8 hours
- Large dataset (>100k records): 1-2 days

## Error Handling and Recovery

### Common Issues
1. **Unmapped users**: Users who haven't completed Supabase migration yet
2. **Data type mismatches**: Ensure proper type conversion
3. **Foreign key violations**: Validate relationships before loading
4. **Duplicate records**: Use conflict resolution strategies

### Recovery Strategies
- Keep detailed logs of all operations
- Use transactions for atomic operations
- Maintain staging tables for rollback capability
- Test with subset of data first

## Best Practices

1. **Always test with a subset first**
2. **Maintain data lineage and audit trails**
3. **Use staging tables for complex transformations**
4. **Validate data at each step**
5. **Plan for partial migration scenarios**
6. **Document any data quality issues found**
7. **Keep legacy system running until verification complete**

## Security Considerations

- **Never migrate passwords or sensitive auth data**
- **Ensure proper access controls during migration**
- **Use service role keys securely**
- **Validate data sanitization for user content**
- **Audit all data access during migration**