"""
Execution model for tracking streaming execution metadata, status, and I/O
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, JSON, DateTime, Integer, Enum as SQLEnum, Index
from db.session import Base
import enum
import uuid


class ExecutionStatus(str, enum.Enum):
    """Execution status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


def generate_execution_id() -> str:
    """Generate execution ID in format exec_{uuid_hex_12_chars}"""
    return f"exec_{uuid.uuid4().hex[:12]}"


class Execution(Base):
    """
    Execution model for tracking streaming execution metadata
    Records execution state, input/output data, token usage, and errors
    """
    __tablename__ = "executions"
    
    # Primary key
    id = Column(String(50), primary_key=True, default=generate_execution_id)
    
    # Foreign keys (indexes defined in __table_args__)
    agent_id = Column(String(50), nullable=False)
    conversation_id = Column(String(50), nullable=True)
    
    # Status (indexes defined in __table_args__)
    status = Column(SQLEnum(ExecutionStatus), nullable=False, default=ExecutionStatus.PENDING)
    
    # Input/Output data
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    
    # Token usage statistics
    prompt_tokens = Column(Integer, nullable=True, default=0)
    completion_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Additional metadata (named extra_metadata to avoid SQLAlchemy reserved name)
    extra_metadata = Column("metadata", JSON, nullable=True)
    
    # Error information
    error_message = Column(String(500), nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # Indexes (explicit naming to avoid conflicts)
    __table_args__ = (
        Index('ix_executions_agent_id', 'agent_id'),
        Index('ix_executions_status', 'status'),
        Index('ix_executions_agent_status', 'agent_id', 'status'),
        Index('ix_executions_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Execution(id={self.id}, status={self.status}, agent_id={self.agent_id})>"
