#!/usr/bin/env python3
"""
ETL Example Script for SQLite to Postgres Migration.

This is a commented template that demonstrates the ETL process for migrating
data from SQLite to Supabase Postgres. It provides patterns and examples
that can be adapted for your specific schema.

DO NOT RUN THIS SCRIPT DIRECTLY - it's a template for building your custom ETL.

Usage:
    1. Copy this script and adapt for your specific schema
    2. Configure your database connections
    3. Test with a small subset of data first
    4. Run in stages with validation at each step

Required dependencies:
    pip install sqlite3 psycopg2-binary pandas python-dotenv
"""

import sqlite3
import csv
import json
import os
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('etl_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SQLiteToPostgresETL:
    """Template class for SQLite to Postgres ETL operations."""
    
    def __init__(self, sqlite_path: str, export_dir: str = "data"):
        self.sqlite_path = sqlite_path
        self.export_dir = export_dir
        
        # Create export directory if it doesn't exist
        os.makedirs(export_dir, exist_ok=True)
        
        logger.info(f"Initialized ETL with SQLite: {sqlite_path}")
        logger.info(f"Export directory: {export_dir}")
    
    def connect_sqlite(self) -> sqlite3.Connection:
        """Create connection to SQLite database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    def export_table_to_csv(self, table_name: str, query: str, filename: str = None) -> str:
        """Export a table or query result to CSV."""
        if filename is None:
            filename = f"export_{table_name}.csv"
        
        filepath = os.path.join(self.export_dir, filename)
        
        try:
            conn = self.connect_sqlite()
            
            # Execute query and fetch results
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No data found for query: {query}")
                return filepath
            
            # Get column names
            columns = [description[0] for description in cursor.description]
            
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                
                for row in rows:
                    # Convert Row object to list for CSV writer
                    writer.writerow([row[col] for col in columns])
            
            logger.info(f"Exported {len(rows)} rows to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export {table_name}: {e}")
            raise
        finally:
            if 'conn' in locals():
                conn.close()
    
    def export_users_mapping(self) -> str:
        """Export user mapping data for ID resolution."""
        query = """
        SELECT 
            id as legacy_user_id,
            email,
            datetime(created_at, 'localtime') as created_at,
            datetime(last_login, 'localtime') as last_login
        FROM users 
        WHERE email IS NOT NULL 
        ORDER BY created_at
        """
        
        return self.export_table_to_csv("users", query, "export_user_mapping.csv")
    
    def export_jobs(self) -> str:
        """Export jobs table with proper formatting."""
        query = """
        SELECT 
            id as legacy_job_id,
            user_id as legacy_user_id,
            job_type,
            status,
            datetime(created_at, 'localtime') as created_at,
            datetime(updated_at, 'localtime') as updated_at,
            source_file,
            result_file,
            -- Handle JSON metadata properly
            CASE 
                WHEN metadata IS NOT NULL THEN metadata
                ELSE '{}'
            END as metadata,
            -- Add any other fields you need
            processing_time_seconds,
            error_message
        FROM jobs 
        ORDER BY created_at
        """
        
        return self.export_table_to_csv("jobs", query, "export_jobs.csv")
    
    def export_credit_transactions(self) -> str:
        """Export credit transactions with proper formatting."""
        query = """
        SELECT 
            id as legacy_transaction_id,
            user_id as legacy_user_id,
            amount,
            transaction_type,
            reference_id,
            datetime(created_at, 'localtime') as created_at,
            description,
            -- Add any other fields you need
            payment_method,
            external_transaction_id
        FROM credit_transactions 
        ORDER BY created_at
        """
        
        return self.export_table_to_csv("credit_transactions", query, "export_credit_transactions.csv")
    
    def validate_export_data(self, filepath: str) -> Dict[str, Any]:
        """Validate exported CSV data."""
        try:
            df = pd.read_csv(filepath)
            
            validation_report = {
                "filepath": filepath,
                "total_rows": len(df),
                "columns": list(df.columns),
                "null_counts": df.isnull().sum().to_dict(),
                "data_types": df.dtypes.to_dict(),
                "sample_data": df.head().to_dict('records')
            }
            
            logger.info(f"Validation for {filepath}:")
            logger.info(f"  Total rows: {validation_report['total_rows']}")
            logger.info(f"  Columns: {validation_report['columns']}")
            
            # Check for common issues
            if 'email' in df.columns:
                invalid_emails = df[~df['email'].str.contains('@', na=False)]
                if len(invalid_emails) > 0:
                    logger.warning(f"Found {len(invalid_emails)} invalid emails")
            
            return validation_report
            
        except Exception as e:
            logger.error(f"Validation failed for {filepath}: {e}")
            raise
    
    def generate_postgres_staging_sql(self) -> str:
        """Generate SQL for creating staging tables in Postgres."""
        sql = """
-- Staging Tables for Data Migration
-- Run this in your Supabase SQL Editor

-- User mapping staging table
CREATE TABLE IF NOT EXISTS stg_user_mapping (
    legacy_user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ,
    last_login TIMESTAMPTZ,
    -- Fields added during processing
    supabase_user_id UUID,
    processed_at TIMESTAMPTZ
);

-- Jobs staging table
CREATE TABLE IF NOT EXISTS stg_jobs (
    legacy_job_id TEXT PRIMARY KEY,
    legacy_user_id TEXT,
    job_type TEXT,
    status TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    source_file TEXT,
    result_file TEXT,
    metadata JSONB,
    processing_time_seconds INTEGER,
    error_message TEXT,
    -- Fields added during processing
    supabase_user_id UUID,
    new_job_id UUID DEFAULT gen_random_uuid(),
    processed_at TIMESTAMPTZ
);

-- Credit transactions staging table
CREATE TABLE IF NOT EXISTS stg_credit_transactions (
    legacy_transaction_id TEXT PRIMARY KEY,
    legacy_user_id TEXT,
    amount INTEGER,
    transaction_type TEXT,
    reference_id TEXT,
    created_at TIMESTAMPTZ,
    description TEXT,
    payment_method TEXT,
    external_transaction_id TEXT,
    -- Fields added during processing
    supabase_user_id UUID,
    new_transaction_id UUID DEFAULT gen_random_uuid(),
    processed_at TIMESTAMPTZ
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_stg_user_mapping_email ON stg_user_mapping(email);
CREATE INDEX IF NOT EXISTS idx_stg_jobs_legacy_user ON stg_jobs(legacy_user_id);
CREATE INDEX IF NOT EXISTS idx_stg_credit_trans_legacy_user ON stg_credit_transactions(legacy_user_id);

-- Permanent legacy mapping table
CREATE TABLE IF NOT EXISTS legacy_user_map (
    legacy_user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    supabase_user_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    migrated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_legacy_user_map_email ON legacy_user_map(email);
CREATE INDEX IF NOT EXISTS idx_legacy_user_map_supabase_id ON legacy_user_map(supabase_user_id);
        """
        
        staging_sql_path = os.path.join(self.export_dir, "create_staging_tables.sql")
        with open(staging_sql_path, 'w') as f:
            f.write(sql)
        
        logger.info(f"Generated staging table SQL: {staging_sql_path}")
        return staging_sql_path
    
    def generate_data_transformation_sql(self) -> str:
        """Generate SQL for data transformation after CSV import."""
        sql = """
-- Data Transformation SQL
-- Run this after importing CSV data into staging tables

-- Step 1: Resolve Supabase user IDs for user mapping
UPDATE stg_user_mapping 
SET supabase_user_id = (
    SELECT p.id 
    FROM profiles p 
    WHERE p.email = stg_user_mapping.email
),
processed_at = NOW()
WHERE email IS NOT NULL;

-- Step 2: Resolve user IDs for jobs
UPDATE stg_jobs 
SET supabase_user_id = (
    SELECT um.supabase_user_id 
    FROM stg_user_mapping um 
    WHERE um.legacy_user_id = stg_jobs.legacy_user_id
),
processed_at = NOW()
WHERE legacy_user_id IS NOT NULL;

-- Step 3: Resolve user IDs for credit transactions
UPDATE stg_credit_transactions 
SET supabase_user_id = (
    SELECT um.supabase_user_id 
    FROM stg_user_mapping um 
    WHERE um.legacy_user_id = stg_credit_transactions.legacy_user_id
),
processed_at = NOW()
WHERE legacy_user_id IS NOT NULL;

-- Step 4: Populate permanent legacy mapping table
INSERT INTO legacy_user_map (legacy_user_id, email, supabase_user_id, migrated_at)
SELECT 
    legacy_user_id,
    email,
    supabase_user_id,
    NOW()
FROM stg_user_mapping 
WHERE supabase_user_id IS NOT NULL
ON CONFLICT (legacy_user_id) DO UPDATE SET
    supabase_user_id = EXCLUDED.supabase_user_id,
    migrated_at = EXCLUDED.migrated_at;
        """
        
        transform_sql_path = os.path.join(self.export_dir, "transform_data.sql")
        with open(transform_sql_path, 'w') as f:
            f.write(sql)
        
        logger.info(f"Generated transformation SQL: {transform_sql_path}")
        return transform_sql_path
    
    def generate_validation_sql(self) -> str:
        """Generate SQL for validating migrated data."""
        sql = """
-- Data Validation Queries
-- Run these to verify successful migration

-- 1. Check mapping success rates
SELECT 
    'User Mapping' as table_name,
    COUNT(*) as total_records,
    COUNT(supabase_user_id) as mapped_records,
    ROUND(COUNT(supabase_user_id) * 100.0 / COUNT(*), 2) as mapping_success_rate
FROM stg_user_mapping
UNION ALL
SELECT 
    'Jobs' as table_name,
    COUNT(*) as total_records,
    COUNT(supabase_user_id) as mapped_records,
    ROUND(COUNT(supabase_user_id) * 100.0 / COUNT(*), 2) as mapping_success_rate
FROM stg_jobs
UNION ALL
SELECT 
    'Credit Transactions' as table_name,
    COUNT(*) as total_records,
    COUNT(supabase_user_id) as mapped_records,
    ROUND(COUNT(supabase_user_id) * 100.0 / COUNT(*), 2) as mapping_success_rate
FROM stg_credit_transactions;

-- 2. Check for unmapped records
SELECT 'Unmapped Users' as issue, COUNT(*) as count
FROM stg_user_mapping WHERE supabase_user_id IS NULL
UNION ALL
SELECT 'Unmapped Jobs' as issue, COUNT(*) as count
FROM stg_jobs WHERE supabase_user_id IS NULL
UNION ALL
SELECT 'Unmapped Transactions' as issue, COUNT(*) as count
FROM stg_credit_transactions WHERE supabase_user_id IS NULL;

-- 3. Data integrity checks
SELECT 
    COUNT(DISTINCT legacy_user_id) as unique_legacy_users,
    COUNT(DISTINCT supabase_user_id) as unique_supabase_users,
    COUNT(*) as total_jobs,
    MIN(created_at) as earliest_job,
    MAX(created_at) as latest_job
FROM stg_jobs 
WHERE supabase_user_id IS NOT NULL;

-- 4. Credit transaction summary
SELECT 
    transaction_type,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount
FROM stg_credit_transactions 
WHERE supabase_user_id IS NOT NULL
GROUP BY transaction_type
ORDER BY transaction_count DESC;
        """
        
        validation_sql_path = os.path.join(self.export_dir, "validate_migration.sql")
        with open(validation_sql_path, 'w') as f:
            f.write(sql)
        
        logger.info(f"Generated validation SQL: {validation_sql_path}")
        return validation_sql_path
    
    def run_full_export(self) -> Dict[str, str]:
        """Run complete export process."""
        logger.info("Starting full export process...")
        
        exports = {}
        
        try:
            # Export all tables
            exports['user_mapping'] = self.export_users_mapping()
            exports['jobs'] = self.export_jobs()
            exports['credit_transactions'] = self.export_credit_transactions()
            
            # Validate exports
            for name, filepath in exports.items():
                logger.info(f"Validating {name}...")
                self.validate_export_data(filepath)
            
            # Generate SQL files
            exports['staging_sql'] = self.generate_postgres_staging_sql()
            exports['transform_sql'] = self.generate_data_transformation_sql()
            exports['validation_sql'] = self.generate_validation_sql()
            
            logger.info("Full export completed successfully!")
            logger.info("Next steps:")
            logger.info("1. Review exported CSV files")
            logger.info("2. Run staging table SQL in Supabase")
            logger.info("3. Import CSV data into staging tables")
            logger.info("4. Run transformation SQL")
            logger.info("5. Run validation queries")
            logger.info("6. Load data into production tables")
            
            return exports
            
        except Exception as e:
            logger.error(f"Export process failed: {e}")
            raise


def main():
    """Example usage of the ETL class."""
    # Configuration
    SQLITE_DB_PATH = "legacy_database.db"  # Update this path
    EXPORT_DIR = "data"
    
    # Check if SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        logger.error(f"SQLite database not found: {SQLITE_DB_PATH}")
        logger.info("Please update SQLITE_DB_PATH to point to your legacy database")
        return
    
    try:
        # Initialize ETL
        etl = SQLiteToPostgresETL(SQLITE_DB_PATH, EXPORT_DIR)
        
        # Run export process
        exports = etl.run_full_export()
        
        print("\n" + "="*50)
        print("ETL EXPORT COMPLETED")
        print("="*50)
        print("Files created:")
        for name, filepath in exports.items():
            print(f"  {name}: {filepath}")
        
        print("\nNext steps:")
        print("1. Review the exported CSV files")
        print("2. Run create_staging_tables.sql in Supabase SQL Editor")
        print("3. Import CSV data into staging tables using Supabase dashboard")
        print("4. Run transform_data.sql to resolve user IDs")
        print("5. Run validate_migration.sql to check data integrity")
        print("6. Load data into production tables when validation passes")
        
    except Exception as e:
        logger.error(f"ETL process failed: {e}")


if __name__ == "__main__":
    # This is a template script - customize before running
    print("WARNING: This is a template script for ETL migration.")
    print("Please review and customize the code before running with real data.")
    print("Update database paths and table schemas as needed.")
    
    # Uncomment the next line after customization
    # main()