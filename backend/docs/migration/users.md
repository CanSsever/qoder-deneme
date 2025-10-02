# User Migration Strategy

This document outlines the strategy for migrating existing users from the legacy SQLite-based authentication system to Supabase Auth.

## Migration Overview

Since the existing auth endpoints have been removed and replaced with Supabase Auth, current users need a way to access their accounts. We provide two migration paths depending on your organizational needs and user base size.

## Path A: Passwordless Migration using Magic Link (Recommended)

This is the recommended approach for most applications as it's simpler, more secure, and doesn't require handling legacy password hashes.

### Process
1. **Export legacy user emails** from SQLite database
2. **Use Supabase Admin API** to invite each email (sends magic link automatically)
3. **Users receive email invitation** and click magic link to authenticate
4. **Profile is created automatically** on first login via `/api/bootstrap-profile` endpoint

### Pros
- No password hash handling required
- More secure (users get fresh authentication)
- Simpler implementation
- Built-in email verification

### Cons
- Users must open their email once to complete migration
- Requires email communication to users

### When to Use
- Production migrations with active user base
- Security-conscious environments
- When you want to ensure email verification

## Path B: Admin Import (Optional/Advanced)

This approach pre-creates user accounts in Supabase but still requires users to reset their passwords.

### Process
1. **Export legacy user data** (emails, metadata)
2. **Use Supabase Auth Admin API** to pre-create user accounts
3. **Do NOT attempt to migrate password hashes** (not supported/secure)
4. **Trigger password reset flow** for all imported users
5. **Link existing data** to new Supabase user IDs

### Pros
- Users see their account exists immediately
- Can pre-populate some profile data
- Batch processing possible

### Cons
- More complex implementation
- Still requires password reset
- Potential for sync issues

### When to Use
- Large user bases where email invitation might be overwhelming
- When you need to migrate additional user metadata
- Advanced use cases with custom user onboarding flows

## Implementation Scripts

### Export Legacy Users

First, export your existing users from SQLite:

```sql
-- Export user emails from legacy database
SELECT email, created_at, last_login 
FROM users 
WHERE email IS NOT NULL 
ORDER BY created_at;
```

Save this as `data/legacy_users.csv` with columns: `email,created_at,last_login`

### Script: Invite Existing Users (Path A)

Use the provided script `tools/invite_existing_users.py` to send magic link invitations:

```bash
# Install required dependencies if not already present
pip install supabase python-dotenv

# Run the invitation script
python tools/invite_existing_users.py --csv data/legacy_users.csv

# Options:
python tools/invite_existing_users.py --csv data/legacy_users.csv --dry-run  # Preview only
python tools/invite_existing_users.py --csv data/legacy_users.csv --batch-size 50  # Smaller batches
```

### Script: Admin Import Users (Path B)

For advanced scenarios, use the admin import approach:

```bash
# Run the admin import script (creates users but requires password reset)
python tools/admin_import_users.py --csv data/legacy_users.csv
```

## Post-Migration Considerations

### Profile Bootstrap
- Users who authenticate via Supabase for the first time will automatically trigger profile creation
- The `/api/bootstrap-profile` endpoint handles this seamlessly
- No manual intervention required for profile setup

### Data Linking
- Legacy user data should be linked using email addresses as the common identifier
- Supabase user IDs will be different from legacy user IDs
- Consider creating a mapping table `legacy_user_map` if needed:
  ```sql
  CREATE TABLE legacy_user_map (
    legacy_user_id TEXT,
    email TEXT,
    supabase_user_id UUID,
    migrated_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```

### Verification
After migration, verify:
- [ ] All users can successfully authenticate
- [ ] Profiles are created automatically on first login
- [ ] User data is correctly associated with new accounts
- [ ] No authentication errors in logs

## Communication Template

Send this email to your users before migration:

```
Subject: Important: Account Migration to Improved Authentication

Hello [User Name],

We're upgrading our authentication system to provide you with a more secure and reliable experience. 

What you need to do:
1. Check your email for a magic link invitation (arriving within 24 hours)
2. Click the link to securely access your account
3. Your account data and credits will be preserved automatically

If you don't receive the email:
- Check your spam folder
- Contact support at [support-email]

Thank you for your patience as we improve our service.

Best regards,
[Your Team]
```

## Migration Checklist

- [ ] Export legacy user emails from SQLite
- [ ] Test invitation script with a small subset of users
- [ ] Send user communication about the migration
- [ ] Run full invitation script: `python tools/invite_existing_users.py --csv data/legacy_users.csv`
- [ ] Monitor invitation email delivery and user logins
- [ ] Verify profile creation is working via `/api/bootstrap-profile`
- [ ] Update client applications to use Supabase Auth
- [ ] Remove legacy authentication code and database tables

## Troubleshooting

### Common Issues
1. **Email delivery problems**: Check Supabase Auth email settings and delivery logs
2. **Users not receiving invitations**: Verify email addresses are valid and check spam folders
3. **Profile creation failures**: Check Supabase database permissions and RLS policies
4. **Authentication errors**: Verify JWT secret and Supabase configuration

### Support Scripts
- `tools/check_migration_status.py` - Check how many users have completed migration
- `tools/resend_invitations.py` - Resend invitations for specific users
- `tools/migration_report.py` - Generate migration completion report

## Security Notes

- Legacy password hashes should NOT be migrated (Supabase uses different algorithms)
- All users will need to authenticate via Supabase's secure flow
- Magic links are single-use and time-limited for security
- Profile data is protected by Row Level Security (RLS) policies