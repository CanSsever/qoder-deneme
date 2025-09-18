"""
Database base utilities and common operations.
"""
from typing import TypeVar, Generic, Type, Optional, List
from uuid import UUID
from sqlmodel import SQLModel, Session, select
from fastapi import Depends
from apps.db.session import get_session

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=SQLModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=SQLModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base CRUD operations class."""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def get(self, session: Session, id: UUID) -> Optional[ModelType]:
        """Get a single record by ID."""
        return session.get(self.model, id)
    
    def get_multi(
        self, 
        session: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records with pagination."""
        statement = select(self.model).offset(skip).limit(limit)
        return session.exec(statement).all()
    
    def create(self, session: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        db_obj = self.model(**obj_in.dict())
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj
    
    def update(
        self,
        session: Session,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType
    ) -> ModelType:
        """Update an existing record."""
        obj_data = obj_in.dict(exclude_unset=True)
        for field, value in obj_data.items():
            setattr(db_obj, field, value)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj
    
    def delete(self, session: Session, *, id: UUID) -> Optional[ModelType]:
        """Delete a record by ID."""
        obj = session.get(self.model, id)
        if obj:
            session.delete(obj)
            session.commit()
        return obj
    
    def get_by_field(
        self, 
        session: Session, 
        field_name: str, 
        value: any
    ) -> Optional[ModelType]:
        """Get a record by a specific field value."""
        statement = select(self.model).where(getattr(self.model, field_name) == value)
        return session.exec(statement).first()


class DatabaseDependency:
    """Database dependency injection helper."""
    
    @staticmethod
    def get_db_session() -> Session:
        """FastAPI dependency to get database session."""
        return Depends(get_session)