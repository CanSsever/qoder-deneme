#!/usr/bin/env python3
"""
Invite existing users to migrate to Supabase Auth.

This script reads a CSV file of legacy user emails and sends magic link
invitations via Supabase Admin API. It's idempotent - won't re-invite
users who already exist in Supabase.

Usage:
    python tools/invite_existing_users.py --csv data/legacy_users.csv
    python tools/invite_existing_users.py --csv data/legacy_users.csv --dry-run
    python tools/invite_existing_users.py --csv data/legacy_users.csv --batch-size 50

Required environment variables:
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY - Service role key for admin operations
"""

import argparse
import csv
import os
import sys
import time
from typing import List, Dict, Any
import logging
from dataclasses import dataclass

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Missing required dependencies. Please install:")
    print("pip install supabase python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_invite.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class InvitationResult:
    """Result of a user invitation attempt."""
    email: str
    success: bool
    message: str
    action: str  # 'invited', 'skipped', 'error'


class UserMigrationInviter:
    """Handles inviting legacy users to Supabase Auth."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.service_role_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required"
            )
        
        if not dry_run:
            self.client = create_client(self.supabase_url, self.service_role_key)
            logger.info("Initialized Supabase client with service role")
        else:
            self.client = None
            logger.info("DRY RUN MODE - No actual invitations will be sent")
    
    def load_legacy_users(self, csv_file: str) -> List[Dict[str, str]]:
        """Load legacy users from CSV file."""
        users = []
        try:
            with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if 'email' not in row:
                        logger.error(f"CSV file must have 'email' column. Found columns: {list(row.keys())}")
                        sys.exit(1)
                    
                    email = row['email'].strip().lower()
                    if email and '@' in email:  # Basic email validation
                        users.append(row)
                    else:
                        logger.warning(f"Skipping invalid email: {email}")
            
            logger.info(f"Loaded {len(users)} valid users from {csv_file}")
            return users
            
        except FileNotFoundError:
            logger.error(f"CSV file not found: {csv_file}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            sys.exit(1)
    
    def check_user_exists(self, email: str) -> bool:
        """Check if user already exists in Supabase Auth."""
        if self.dry_run:
            return False  # In dry run, assume no users exist
        
        try:
            # Use admin API to check if user exists
            response = self.client.auth.admin.list_users()
            existing_emails = {user.email.lower() for user in response if user.email}
            return email.lower() in existing_emails
        except Exception as e:
            logger.error(f"Error checking if user exists {email}: {e}")
            return False  # Assume doesn't exist on error
    
    def invite_user(self, email: str) -> InvitationResult:
        """Invite a single user via Supabase Admin API."""
        try:
            # Check if user already exists
            if self.check_user_exists(email):
                return InvitationResult(
                    email=email,
                    success=True,
                    message="User already exists in Supabase",
                    action="skipped"
                )
            
            if self.dry_run:
                return InvitationResult(
                    email=email,
                    success=True,
                    message="Would invite user (dry run)",
                    action="invited"
                )
            
            # Send invitation via admin API
            response = self.client.auth.admin.invite_user_by_email(email)
            
            if response:
                logger.info(f"Successfully invited: {email}")
                return InvitationResult(
                    email=email,
                    success=True,
                    message="Invitation sent successfully",
                    action="invited"
                )
            else:
                logger.warning(f"No response for invitation: {email}")
                return InvitationResult(
                    email=email,
                    success=False,
                    message="No response from Supabase",
                    action="error"
                )
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to invite {email}: {error_msg}")
            return InvitationResult(
                email=email,
                success=False,
                message=f"Error: {error_msg}",
                action="error"
            )
    
    def invite_users_batch(self, users: List[Dict[str, str]], batch_size: int = 10) -> List[InvitationResult]:
        """Invite users in batches with rate limiting."""
        results = []
        total_users = len(users)
        
        logger.info(f"Starting invitation process for {total_users} users (batch size: {batch_size})")
        
        for i in range(0, total_users, batch_size):
            batch = users[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_users + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} users)")
            
            for user in batch:
                email = user['email'].strip().lower()
                result = self.invite_user(email)
                results.append(result)
                
                # Small delay between invitations to avoid rate limits
                time.sleep(0.5)
            
            # Longer delay between batches
            if i + batch_size < total_users:
                logger.info(f"Completed batch {batch_num}, waiting 2 seconds before next batch...")
                time.sleep(2)
        
        return results
    
    def generate_report(self, results: List[InvitationResult]) -> None:
        """Generate a summary report of the invitation process."""
        total = len(results)
        invited = sum(1 for r in results if r.action == "invited" and r.success)
        skipped = sum(1 for r in results if r.action == "skipped")
        errors = sum(1 for r in results if r.action == "error")
        
        logger.info("\n" + "="*50)
        logger.info("INVITATION SUMMARY REPORT")
        logger.info("="*50)
        logger.info(f"Total users processed: {total}")
        logger.info(f"Successfully invited: {invited}")
        logger.info(f"Already existed (skipped): {skipped}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Success rate: {((invited + skipped) / total * 100):.1f}%")
        
        if errors > 0:
            logger.info("\nERRORS:")
            for result in results:
                if result.action == "error":
                    logger.info(f"  - {result.email}: {result.message}")
        
        # Write detailed report to file
        report_file = "migration_invite_report.csv"
        with open(report_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['email', 'success', 'action', 'message'])
            for result in results:
                writer.writerow([result.email, result.success, result.action, result.message])
        
        logger.info(f"\nDetailed report written to: {report_file}")


def main():
    """Main function to handle CLI arguments and execute invitation process."""
    parser = argparse.ArgumentParser(
        description="Invite legacy users to migrate to Supabase Auth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/invite_existing_users.py --csv data/legacy_users.csv
  python tools/invite_existing_users.py --csv data/legacy_users.csv --dry-run
  python tools/invite_existing_users.py --csv data/legacy_users.csv --batch-size 50

CSV Format:
  The CSV file should have at minimum an 'email' column:
  email,created_at,last_login
  user1@example.com,2023-01-01,2023-12-01
  user2@example.com,2023-02-01,2023-11-15
        """
    )
    
    parser.add_argument(
        '--csv',
        required=True,
        help='Path to CSV file containing legacy user emails'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview the actions without actually sending invitations'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of users to process in each batch (default: 10)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize inviter
        inviter = UserMigrationInviter(dry_run=args.dry_run)
        
        # Load users from CSV
        users = inviter.load_legacy_users(args.csv)
        
        if not users:
            logger.error("No valid users found in CSV file")
            sys.exit(1)
        
        # Confirm before proceeding (unless dry run)
        if not args.dry_run:
            print(f"\nReady to invite {len(users)} users to Supabase Auth.")
            print("This will send email invitations to all users.")
            confirm = input("Do you want to proceed? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                print("Operation cancelled.")
                sys.exit(0)
        
        # Process invitations
        results = inviter.invite_users_batch(users, batch_size=args.batch_size)
        
        # Generate report
        inviter.generate_report(results)
        
        # Exit with error code if there were failures
        errors = sum(1 for r in results if r.action == "error")
        if errors > 0:
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()