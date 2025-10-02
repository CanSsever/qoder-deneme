-- Storage RLS Policies Patch for Supabase
-- This file contains idempotent SQL to fix storage policies with correct syntax
-- Run this in your Supabase SQL Editor

-- Note: Buckets 'uploads' and 'outputs' must exist before running these policies
-- Create them manually in the Supabase Dashboard > Storage if they don't exist

-- Enable RLS on storage.objects (should already be enabled by Supabase)
-- This is just for completeness - Supabase manages this automatically

-- Drop existing policies if they exist (for idempotency)
DO $$
BEGIN
    -- Drop read policy if exists
    IF EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname='storage' AND tablename='objects' AND policyname='read_own_files_like'
    ) THEN
        DROP POLICY "read_own_files_like" ON storage.objects;
    END IF;

    -- Drop upload policy if exists
    IF EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname='storage' AND tablename='objects' AND policyname='upload_own_files_like'
    ) THEN
        DROP POLICY "upload_own_files_like" ON storage.objects;
    END IF;

    -- Drop update policy if exists
    IF EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname='storage' AND tablename='objects' AND policyname='update_own_files_like'
    ) THEN
        DROP POLICY "update_own_files_like" ON storage.objects;
    END IF;

    -- Drop delete policy if exists
    IF EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname='storage' AND tablename='objects' AND policyname='delete_own_files_like'
    ) THEN
        DROP POLICY "delete_own_files_like" ON storage.objects;
    END IF;
END$$;

-- Create RLS policies with correct SQL syntax using LIKE pattern matching
DO $$
BEGIN
    -- Policy for reading own files
    -- Files must be in user's folder: auth.uid()::text || '/%'
    CREATE POLICY "read_own_files_like" ON storage.objects
        FOR SELECT USING (
            bucket_id IN ('uploads', 'outputs')
            AND name LIKE auth.uid()::text || '/%'
        );

    -- Policy for uploading files to own folder
    CREATE POLICY "upload_own_files_like" ON storage.objects
        FOR INSERT WITH CHECK (
            bucket_id IN ('uploads', 'outputs')
            AND name LIKE auth.uid()::text || '/%'
        );

    -- Policy for updating own files
    CREATE POLICY "update_own_files_like" ON storage.objects
        FOR UPDATE USING (
            bucket_id IN ('uploads', 'outputs')
            AND name LIKE auth.uid()::text || '/%'
        )
        WITH CHECK (
            bucket_id IN ('uploads', 'outputs')
            AND name LIKE auth.uid()::text || '/%'
        );

    -- Policy for deleting own files
    CREATE POLICY "delete_own_files_like" ON storage.objects
        FOR DELETE USING (
            bucket_id IN ('uploads', 'outputs')
            AND name LIKE auth.uid()::text || '/%'
        );

    -- Log successful policy creation
    RAISE NOTICE 'Storage RLS policies created successfully';

EXCEPTION WHEN OTHERS THEN
    -- Log any errors but don't fail the transaction
    RAISE NOTICE 'Error creating storage policies: %', SQLERRM;
    RAISE;
END$$;

-- Verify policies were created correctly
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies 
WHERE schemaname = 'storage' 
AND tablename = 'objects' 
AND policyname LIKE '%_own_files_like'
ORDER BY policyname;

-- Additional policy for service role operations (if needed)
-- This allows the service role to manage files for system operations
DO $$
BEGIN
    -- Drop existing service role policy if exists
    IF EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE schemaname='storage' AND tablename='objects' AND policyname='service_role_storage_access'
    ) THEN
        DROP POLICY "service_role_storage_access" ON storage.objects;
    END IF;

    -- Create service role policy for admin operations
    CREATE POLICY "service_role_storage_access" ON storage.objects
        FOR ALL USING (
            auth.jwt() ->> 'role' = 'service_role'
        )
        WITH CHECK (
            auth.jwt() ->> 'role' = 'service_role'
        );

    RAISE NOTICE 'Service role storage policy created successfully';

EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Error creating service role storage policy: %', SQLERRM;
    RAISE;
END$$;

-- Create a function to validate file path ownership (optional utility)
CREATE OR REPLACE FUNCTION storage.validate_user_file_path(file_path TEXT, user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Check if the file path starts with the user's UUID
    RETURN file_path LIKE user_id::text || '/%';
END;
$$;

-- Grant execute permission on the validation function
GRANT EXECUTE ON FUNCTION storage.validate_user_file_path TO authenticated, service_role;

-- Comment explaining the RLS structure
COMMENT ON POLICY "read_own_files_like" ON storage.objects IS 
'Allows users to read files in their own folder (/{user_id}/*)';

COMMENT ON POLICY "upload_own_files_like" ON storage.objects IS 
'Allows users to upload files to their own folder (/{user_id}/*)';

COMMENT ON POLICY "update_own_files_like" ON storage.objects IS 
'Allows users to update metadata of files in their own folder (/{user_id}/*)';

COMMENT ON POLICY "delete_own_files_like" ON storage.objects IS 
'Allows users to delete files from their own folder (/{user_id}/*)';

COMMENT ON POLICY "service_role_storage_access" ON storage.objects IS 
'Allows service role to manage all storage objects for admin operations';

-- Create index for better performance on storage.objects
-- Note: These might already exist in Supabase
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_storage_objects_bucket_name 
ON storage.objects(bucket_id, name);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_storage_objects_name_pattern 
ON storage.objects(name text_pattern_ops) 
WHERE bucket_id IN ('uploads', 'outputs');

-- Final verification query
SELECT 
    'Storage RLS Setup Complete' as status,
    COUNT(*) as policy_count
FROM pg_policies 
WHERE schemaname = 'storage' 
AND tablename = 'objects';

-- Example usage in application code:
/*
File path structure should be:
- uploads/{user_id}/source-image.jpg
- outputs/{user_id}/result-image.jpg

Example valid paths:
- uploads/550e8400-e29b-41d4-a716-446655440000/photo.jpg
- outputs/550e8400-e29b-41d4-a716-446655440000/swapped.jpg

Invalid paths (will be blocked by RLS):
- uploads/other-user-id/photo.jpg
- public/shared-file.jpg
- outputs/admin/system-file.jpg
*/