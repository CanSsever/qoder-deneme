-- Complete Supabase Setup Script
-- Run this script in your Supabase SQL Editor to set up the entire database

-- Execute schema creation
\i schema.sql

-- Execute RLS policies
\i rls_policies.sql

-- Execute atomic functions
\i functions.sql

-- Execute storage configuration
\i storage.sql

-- Create indexes for better performance (additional ones)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_user_status ON public.jobs(user_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_jobs_type_status ON public.jobs(job_type, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_credit_transactions_user_type ON public.credit_transactions(user_id, transaction_type);

-- Create a view for user job statistics
CREATE OR REPLACE VIEW public.user_job_stats AS
SELECT 
    user_id,
    COUNT(*) as total_jobs,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
    COUNT(*) FILTER (WHERE status = 'processing') as processing_jobs,
    MAX(created_at) as last_job_created
FROM public.jobs
GROUP BY user_id;

-- Grant access to the view
GRANT SELECT ON public.user_job_stats TO authenticated, service_role;

-- Create a view for user credit summary
CREATE OR REPLACE VIEW public.user_credit_summary AS
SELECT 
    p.id as user_id,
    p.email,
    p.credits as current_credits,
    p.subscription_status,
    COALESCE(SUM(ct.amount) FILTER (WHERE ct.transaction_type = 'credit'), 0) as total_credits_earned,
    COALESCE(SUM(ABS(ct.amount)) FILTER (WHERE ct.transaction_type = 'debit'), 0) as total_credits_spent,
    COUNT(ct.*) as total_transactions
FROM public.profiles p
LEFT JOIN public.credit_transactions ct ON p.id = ct.user_id
GROUP BY p.id, p.email, p.credits, p.subscription_status;

-- Grant access to the view
GRANT SELECT ON public.user_credit_summary TO authenticated, service_role;

-- Enable real-time subscriptions for jobs table (for live updates)
ALTER PUBLICATION supabase_realtime ADD TABLE public.jobs;

NOTIFY pgrst, 'reload schema';