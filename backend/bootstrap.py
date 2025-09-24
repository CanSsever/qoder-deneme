"""
Bootstrap script for OneShot Face Swapper Backend.

This script initializes the application with default data:
- Default user entitlements for existing users
- Plan templates verification
- Database migrations
- Development seed data
"""

import asyncio
import sys
from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select
import structlog

from apps.core.settings import settings
from apps.db.session import engine
from apps.db.models.user import User
from apps.db.models.subscription import UserEntitlement, PLAN_TEMPLATES
from apps.api.services.entitlements import EntitlementsService

logger = structlog.get_logger(__name__)


def bootstrap_entitlements():
    """
    Bootstrap default entitlements for all users who don't have any.
    
    This ensures all existing users get the default plan entitlements.
    """
    try:
        with Session(engine) as session:
            # Get all users
            users = session.exec(select(User)).all()
            logger.info(f"Found {len(users)} users to process")
            
            users_processed = 0
            users_skipped = 0
            
            with EntitlementsService(session) as entitlements:
                for user in users:
                    # Check if user already has entitlements
                    existing_entitlement = entitlements.get_user_entitlement(str(user.id))
                    
                    if existing_entitlement:
                        users_skipped += 1
                        logger.debug(f"User {user.id} already has entitlement: {existing_entitlement.plan_code}")
                        continue
                    
                    # Create default entitlement
                    default_plan = settings.entitlements_default_plan
                    entitlement = entitlements.create_entitlement(
                        user_id=str(user.id),
                        plan_code=default_plan,
                        effective_from=datetime.utcnow()
                    )
                    
                    users_processed += 1
                    logger.info(f"Created {default_plan} entitlement for user {user.id}")
            
            logger.info(
                f"Bootstrap entitlements completed. Processed: {users_processed}, Skipped: {users_skipped}"
            )
            
            return users_processed, users_skipped
            
    except Exception as e:
        logger.error(f"Failed to bootstrap entitlements: {e}")
        raise


def verify_plan_templates():
    """Verify that all plan templates are valid."""
    try:
        logger.info("Verifying plan templates...")
        
        for plan_code, template in PLAN_TEMPLATES.items():
            limits = template["limits"]
            
            # Verify required fields
            required_fields = ["daily_jobs", "concurrent_jobs", "max_side", "features"]
            for field in required_fields:
                if field not in limits:
                    raise ValueError(f"Plan {plan_code} missing required field: {field}")
            
            # Verify field types and ranges
            if not isinstance(limits["daily_jobs"], int) or limits["daily_jobs"] < 0:
                raise ValueError(f"Plan {plan_code} has invalid daily_jobs value")
            
            if not isinstance(limits["concurrent_jobs"], int) or limits["concurrent_jobs"] < 1:
                raise ValueError(f"Plan {plan_code} has invalid concurrent_jobs value")
            
            if not isinstance(limits["max_side"], int) or limits["max_side"] < 64:
                raise ValueError(f"Plan {plan_code} has invalid max_side value")
            
            if not isinstance(limits["features"], list):
                raise ValueError(f"Plan {plan_code} has invalid features value")
            
            logger.info(f"Plan {plan_code} validated successfully")
        
        logger.info("All plan templates are valid")
        return True
        
    except Exception as e:
        logger.error(f"Plan template validation failed: {e}")
        raise


def create_development_users():
    """Create development test users if in development mode."""
    if not settings.is_development:
        logger.info("Not in development mode, skipping test user creation")
        return []
    
    try:
        from apps.core.security import get_password_hash
        
        test_users = [
            {
                "email": "free@test.com",
                "password": "testpass123",
                "plan": "free"
            },
            {
                "email": "pro@test.com", 
                "password": "testpass123",
                "plan": "pro"
            },
            {
                "email": "premium@test.com",
                "password": "testpass123", 
                "plan": "premium"
            }
        ]
        
        created_users = []
        
        with Session(engine) as session:
            with EntitlementsService(session) as entitlements:
                for user_data in test_users:
                    # Check if user already exists
                    existing_user = session.exec(
                        select(User).where(User.email == user_data["email"])
                    ).first()
                    
                    if existing_user:
                        logger.info(f"Test user {user_data['email']} already exists")
                        continue
                    
                    # Create user
                    user = User(
                        email=user_data["email"],
                        hashed_password=get_password_hash(user_data["password"]),
                        credits=100  # Give test users some credits
                    )
                    
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                    
                    # Create entitlement
                    entitlement = entitlements.create_entitlement(
                        user_id=str(user.id),
                        plan_code=user_data["plan"],
                        effective_from=datetime.utcnow()
                    )
                    
                    created_users.append({
                        "user_id": str(user.id),
                        "email": user.email,
                        "plan": user_data["plan"]
                    })
                    
                    logger.info(f"Created test user {user.email} with {user_data['plan']} plan")
        
        return created_users
        
    except Exception as e:
        logger.error(f"Failed to create development users: {e}")
        raise


def run_database_migrations():
    """Run any pending database migrations."""
    try:
        import subprocess
        
        logger.info("Running database migrations...")
        
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        if result.returncode == 0:
            logger.info("Database migrations completed successfully")
            if result.stdout:
                logger.info(f"Migration output: {result.stdout}")
        else:
            logger.error(f"Migration failed: {result.stderr}")
            raise RuntimeError(f"Migration failed: {result.stderr}")
        
        return True
        
    except FileNotFoundError:
        logger.warning("Alembic not found, skipping migrations")
        return False
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise


def bootstrap_database():
    """Bootstrap the entire database with initial data."""
    try:
        logger.info("Starting database bootstrap...")
        
        # Run migrations first
        run_database_migrations()
        
        # Verify plan templates
        verify_plan_templates()
        
        # Bootstrap entitlements for existing users
        users_processed, users_skipped = bootstrap_entitlements()
        
        # Create development users if in dev mode
        dev_users = create_development_users()
        
        logger.info(
            "Database bootstrap completed successfully",
            users_processed=users_processed,
            users_skipped=users_skipped,
            dev_users_created=len(dev_users)
        )
        
        return {
            "success": True,
            "users_processed": users_processed,
            "users_skipped": users_skipped,
            "dev_users_created": len(dev_users),
            "dev_users": dev_users
        }
        
    except Exception as e:
        logger.error(f"Database bootstrap failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """Main bootstrap function."""
    print("OneShot Face Swapper - Database Bootstrap")
    print("=" * 50)
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder(),
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Run bootstrap
    result = bootstrap_database()
    
    if result["success"]:
        print("\\nBootstrap completed successfully!")
        print(f"- Users processed: {result['users_processed']}")
        print(f"- Users skipped: {result['users_skipped']}")
        
        if result["dev_users_created"] > 0:
            print(f"\\nDevelopment users created: {result['dev_users_created']}")
            for user in result["dev_users"]:
                print(f"  - {user['email']} ({user['plan']} plan)")
            print("\\nDefault password for test users: testpass123")
        
        print("\\nApplication is ready to use!")
        sys.exit(0)
    else:
        print(f"\\nBootstrap failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()