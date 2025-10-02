-- Atomic Credit Operation Functions for Supabase AI Processing Platform
-- These functions ensure credit operations are atomic and prevent race conditions

-- Function to increment user credits atomically
CREATE OR REPLACE FUNCTION public.increment_credits(
    target_user_id uuid,
    credit_amount integer
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    affected_rows integer;
BEGIN
    -- Validate input parameters
    IF target_user_id IS NULL OR credit_amount IS NULL THEN
        RAISE EXCEPTION 'User ID and credit amount are required';
    END IF;
    
    IF credit_amount = 0 THEN
        RETURN true; -- No-op for zero credits
    END IF;
    
    -- Update user credits atomically
    UPDATE public.profiles 
    SET credits = credits + credit_amount,
        updated_at = now()
    WHERE id = target_user_id;
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    
    -- Check if user exists
    IF affected_rows = 0 THEN
        RAISE EXCEPTION 'User not found: %', target_user_id;
    END IF;
    
    -- Create credit transaction record
    INSERT INTO public.credit_transactions (
        user_id,
        amount,
        transaction_type,
        metadata
    ) VALUES (
        target_user_id,
        credit_amount,
        CASE 
            WHEN credit_amount > 0 THEN 'credit'
            ELSE 'debit'
        END,
        jsonb_build_object(
            'operation', 'increment_credits',
            'timestamp', now()
        )
    );
    
    RETURN true;
END;
$$;

-- Function to validate and debit credits atomically
CREATE OR REPLACE FUNCTION public.validate_and_debit_credits(
    target_user_id uuid,
    credit_amount integer,
    job_ref_id uuid DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    current_credits integer;
    affected_rows integer;
BEGIN
    -- Validate input parameters
    IF target_user_id IS NULL OR credit_amount IS NULL THEN
        RAISE EXCEPTION 'User ID and credit amount are required';
    END IF;
    
    IF credit_amount <= 0 THEN
        RAISE EXCEPTION 'Credit amount must be positive';
    END IF;
    
    -- Lock the user profile row and get current credits
    SELECT credits INTO current_credits
    FROM public.profiles 
    WHERE id = target_user_id
    FOR UPDATE;
    
    -- Check if user exists
    IF current_credits IS NULL THEN
        RAISE EXCEPTION 'User not found: %', target_user_id;
    END IF;
    
    -- Check if user has sufficient credits
    IF current_credits < credit_amount THEN
        RETURN false; -- Insufficient credits
    END IF;
    
    -- Debit credits atomically
    UPDATE public.profiles 
    SET credits = credits - credit_amount,
        updated_at = now()
    WHERE id = target_user_id;
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    
    -- Sanity check
    IF affected_rows = 0 THEN
        RAISE EXCEPTION 'Failed to update user credits';
    END IF;
    
    -- Create credit transaction record
    INSERT INTO public.credit_transactions (
        user_id,
        amount,
        transaction_type,
        job_id,
        metadata
    ) VALUES (
        target_user_id,
        -credit_amount, -- Negative amount for debit
        'debit',
        job_ref_id,
        jsonb_build_object(
            'operation', 'validate_and_debit_credits',
            'timestamp', now()
        )
    );
    
    RETURN true;
END;
$$;

-- Function to get user credits safely
CREATE OR REPLACE FUNCTION public.get_user_credits(target_user_id uuid)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    user_credits integer;
BEGIN
    SELECT credits INTO user_credits
    FROM public.profiles 
    WHERE id = target_user_id;
    
    RETURN COALESCE(user_credits, 0);
END;
$$;

-- Function to refund credits for failed jobs
CREATE OR REPLACE FUNCTION public.refund_job_credits(
    target_user_id uuid,
    job_ref_id uuid,
    refund_amount integer
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    affected_rows integer;
BEGIN
    -- Validate input parameters
    IF target_user_id IS NULL OR job_ref_id IS NULL OR refund_amount IS NULL THEN
        RAISE EXCEPTION 'User ID, job ID, and refund amount are required';
    END IF;
    
    IF refund_amount <= 0 THEN
        RAISE EXCEPTION 'Refund amount must be positive';
    END IF;
    
    -- Refund credits atomically
    UPDATE public.profiles 
    SET credits = credits + refund_amount,
        updated_at = now()
    WHERE id = target_user_id;
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    
    -- Check if user exists
    IF affected_rows = 0 THEN
        RAISE EXCEPTION 'User not found: %', target_user_id;
    END IF;
    
    -- Create refund transaction record
    INSERT INTO public.credit_transactions (
        user_id,
        amount,
        transaction_type,
        job_id,
        metadata
    ) VALUES (
        target_user_id,
        refund_amount,
        'refund',
        job_ref_id,
        jsonb_build_object(
            'operation', 'refund_job_credits',
            'timestamp', now(),
            'reason', 'job_failed'
        )
    );
    
    RETURN true;
END;
$$;

-- Function to bootstrap user profile (for new registrations)
CREATE OR REPLACE FUNCTION public.bootstrap_user_profile(
    user_id uuid,
    user_email text,
    initial_credits integer DEFAULT 10
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Validate input parameters
    IF user_id IS NULL OR user_email IS NULL THEN
        RAISE EXCEPTION 'User ID and email are required';
    END IF;
    
    -- Insert user profile (will fail if already exists due to primary key constraint)
    INSERT INTO public.profiles (
        id,
        email,
        credits,
        subscription_status
    ) VALUES (
        user_id,
        user_email,
        COALESCE(initial_credits, 10),
        'inactive'
    );
    
    -- Create initial credit transaction if credits > 0
    IF initial_credits > 0 THEN
        INSERT INTO public.credit_transactions (
            user_id,
            amount,
            transaction_type,
            metadata
        ) VALUES (
            user_id,
            initial_credits,
            'bonus',
            jsonb_build_object(
                'operation', 'bootstrap_user_profile',
                'timestamp', now(),
                'reason', 'welcome_bonus'
            )
        );
    END IF;
    
    RETURN user_id;
END;
$$;

-- Grant necessary permissions to authenticated users
GRANT EXECUTE ON FUNCTION public.increment_credits(uuid, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.validate_and_debit_credits(uuid, integer, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_user_credits(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.refund_job_credits(uuid, uuid, integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.bootstrap_user_profile(uuid, text, integer) TO authenticated;

-- Grant service role permissions for backend operations
GRANT EXECUTE ON FUNCTION public.increment_credits(uuid, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.validate_and_debit_credits(uuid, integer, uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.get_user_credits(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.refund_job_credits(uuid, uuid, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.bootstrap_user_profile(uuid, text, integer) TO service_role;