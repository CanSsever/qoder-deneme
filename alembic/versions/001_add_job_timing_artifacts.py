"""Add job timing fields and artifacts table

Revision ID: 001_add_job_timing_artifacts
Revises: 
Create Date: 2025-09-17 17:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001_add_job_timing_artifacts'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to jobs table
    op.add_column('jobs', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('jobs', sa.Column('finished_at', sa.DateTime(), nullable=True))
    
    # Create artifacts table
    op.create_table('artifacts',
        sa.Column('artifact_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('job_id', sa.String(), nullable=False),
        sa.Column('output_url', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_artifacts_job_id', 'artifacts', ['job_id'])


def downgrade() -> None:
    # Drop artifacts table
    op.drop_index('ix_artifacts_job_id', 'artifacts')
    op.drop_table('artifacts')
    
    # Remove columns from jobs table
    op.drop_column('jobs', 'finished_at')
    op.drop_column('jobs', 'started_at')