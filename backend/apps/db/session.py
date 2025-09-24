"""
Database connection and session management.
"""
from sqlmodel import create_engine, SQLModel, Session
from apps.core.settings import settings


# Create database engine
engine = create_engine(
    settings.database_url,
    echo=settings.is_development,  # Log SQL queries in development
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,  # Recycle connections every 5 minutes
)


def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session