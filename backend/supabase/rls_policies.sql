-- Row Level Security Policies for Supabase AI Processing Platform
-- This file contains all RLS policies to ensure users can only access their own data

-- Profiles table policies
-- Users can only see and update their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Jobs table policies
-- Users can only see their own jobs
CREATE POLICY "Users can view own jobs" ON public.jobs
    FOR SELECT USING (auth.uid() = user_id);

-- Users can only create jobs for themselves
CREATE POLICY "Users can create own jobs" ON public.jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can only update their own jobs
CREATE POLICY "Users can update own jobs" ON public.jobs
    FOR UPDATE USING (auth.uid() = user_id);

-- Users can only delete their own jobs (if needed)
CREATE POLICY "Users can delete own jobs" ON public.jobs
    FOR DELETE USING (auth.uid() = user_id);

-- Credit transactions table policies
-- Users can only see their own credit transactions
CREATE POLICY "Users can view own credit transactions" ON public.credit_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Users can only create credit transactions for themselves
CREATE POLICY "Users can create own credit transactions" ON public.credit_transactions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Service role policies (for backend operations)
-- Allow service role to perform all operations (for system functions)
CREATE POLICY "Service role can manage all profiles" ON public.profiles
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role can manage all jobs" ON public.jobs
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role can manage all credit transactions" ON public.credit_transactions
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');