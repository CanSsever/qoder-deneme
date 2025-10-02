-- Supabase Storage Configuration for AI Processing Platform
-- This file contains bucket creation and policies for file storage

-- Create storage buckets
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES 
    ('uploads', 'uploads', false, 20971520, ARRAY['image/jpeg', 'image/png', 'image/webp']), -- 20MB limit
    ('outputs', 'outputs', false, 20971520, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO NOTHING;

-- Storage policies for uploads bucket
-- Users can upload files to their own directory
CREATE POLICY "Users can upload to own directory" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'uploads' AND 
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- Users can view their own uploaded files
CREATE POLICY "Users can view own uploads" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'uploads' AND 
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- Users can delete their own uploaded files
CREATE POLICY "Users can delete own uploads" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'uploads' AND 
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- Storage policies for outputs bucket
-- Users can view their own output files
CREATE POLICY "Users can view own outputs" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'outputs' AND 
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- Only service role can upload to outputs bucket (for AI processing results)
CREATE POLICY "Service role can upload outputs" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'outputs' AND 
        auth.jwt() ->> 'role' = 'service_role'
    );

-- Service role can manage all files (for cleanup, etc.)
CREATE POLICY "Service role can manage all files" ON storage.objects
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');