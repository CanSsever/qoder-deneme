"""Add payment and entitlement tables

Revision ID: 002_add_payment_entitlements
Revises: 001_add_job_timing_artifacts
Create Date: 2024-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '002_add_payment_entitlements'
down_revision = '001_add_job_timing_artifacts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create payment and entitlement tables."""
    
    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('raw_payload_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_subscription_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.UniqueConstraint('event_id')
    )
    
    # Create indexes for subscriptions
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_product_id', 'subscriptions', ['product_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('ix_subscriptions_event_id', 'subscriptions', ['event_id'])
    
    # Create user_entitlements table
    op.create_table(
        'user_entitlements',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('plan_code', sa.String(), nullable=False),
        sa.Column('limits_json', sa.Text(), nullable=False),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    
    # Create indexes for user_entitlements
    op.create_index('ix_user_entitlements_user_id', 'user_entitlements', ['user_id'])
    op.create_index('ix_user_entitlements_plan_code', 'user_entitlements', ['plan_code'])
    
    # Create usage_aggregates table
    op.create_table(
        'usage_aggregates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('jobs_created', sa.Integer(), nullable=False),
        sa.Column('jobs_completed', sa.Integer(), nullable=False),
        sa.Column('jobs_failed', sa.Integer(), nullable=False),
        sa.Column('total_processing_time_seconds', sa.Integer(), nullable=False),
        sa.Column('total_credits_consumed', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    
    # Create indexes for usage_aggregates
    op.create_index('ix_usage_aggregates_user_id', 'usage_aggregates', ['user_id'])
    op.create_index('ix_usage_aggregates_date', 'usage_aggregates', ['date'])
    
    # Create composite unique index for user_id + date
    op.create_index('ix_usage_aggregates_user_date', 'usage_aggregates', ['user_id', 'date'], unique=True)


def downgrade() -> None:
    """Drop payment and entitlement tables."""
    
    # Drop indexes first
    op.drop_index('ix_usage_aggregates_user_date', 'usage_aggregates')
    op.drop_index('ix_usage_aggregates_date', 'usage_aggregates')
    op.drop_index('ix_usage_aggregates_user_id', 'usage_aggregates')
    
    op.drop_index('ix_user_entitlements_plan_code', 'user_entitlements')
    op.drop_index('ix_user_entitlements_user_id', 'user_entitlements')
    
    op.drop_index('ix_subscriptions_event_id', 'subscriptions')
    op.drop_index('ix_subscriptions_status', 'subscriptions')
    op.drop_index('ix_subscriptions_product_id', 'subscriptions')
    op.drop_index('ix_subscriptions_user_id', 'subscriptions')
    
    # Drop tables
    op.drop_table('usage_aggregates')
    op.drop_table('user_entitlements')
    op.drop_table('subscriptions')