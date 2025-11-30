from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class Runtime(str, enum.Enum):
    PYTHON = "python"
    NODEJS = "nodejs"


class ExecutionType(str, enum.Enum):
    SYNC = "sync"
    ASYNC = "async"


class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=False, index=True, nullable=False)
    runtime = Column(Enum(Runtime), nullable=False)
    code = Column(Text, nullable=False)
    execution_type = Column(Enum(ExecutionType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    jobs = relationship("Job", back_populates="function")