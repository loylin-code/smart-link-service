"""
SQLAlchemy models for SmartLink
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, JSON, DateTime, Integer, 
    Boolean, Enum as SQLEnum, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from db.session import Base


class AppStatus(str, enum.Enum):
    """Application status enum"""
    DRAFT = "draft"
    DESIGNING = "designing"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AppType(str, enum.Enum):
    """Application type enum"""
    WORKFLOW = "workflow"
    CHART = "chart"
    FORM = "form"
    DASHBOARD = "dashboard"
    CUSTOM = "custom"


class ResourceStatus(str, enum.Enum):
    """Resource status enum"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class Application(Base):
    """Application model"""
    __tablename__ = "applications"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    type = Column(SQLEnum(AppType), default=AppType.CUSTOM, nullable=False)
    status = Column(SQLEnum(AppStatus), default=AppStatus.DRAFT, nullable=False)
    version = Column(String(20), default="0.1.0", nullable=False)
    
    # Application flow schema (nodes and edges)
    schema = Column(JSON, default=dict, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # User association (for future multi-tenancy)
    user_id = Column(String, nullable=True, index=True)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="application", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_applications_status_type', 'status', 'type'),
    )
    
    def __repr__(self):
        return f"<Application(id={self.id}, name={self.name}, status={self.status})>"


class Conversation(Base):
    """Conversation model"""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    app_id = Column(String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title})>"


class Message(Base):
    """Message model"""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(JSON, nullable=False)  # Support multimodal content
    
    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"


class Skill(Base):
    """Skill model"""
    __tablename__ = "skills"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=False)  # builtin, custom
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # Skill configuration
    config = Column(JSON, default=dict, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<Skill(id={self.id}, name={self.name}, type={self.type})>"


class MCPServer(Base):
    """MCP Server model"""
    __tablename__ = "mcp_servers"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=True)  # stdio, sse, etc.
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # MCP Server configuration
    endpoint = Column(String(500), nullable=True)  # URL or command
    config = Column(JSON, default=dict, nullable=False)  # args, env, etc.
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name={self.name})>"


class Component(Base):
    """Frontend component metadata model"""
    __tablename__ = "components"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=False)
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # Component metadata
    path = Column(String(500), nullable=False)  # Component file path
    meta = Column(JSON, default=dict, nullable=False)  # Props, events, slots
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<Component(id={self.id}, name={self.name})>"


class APIKey(Base):
    """API Key model (for future multi-tenancy)"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, index=True)
    key = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    user_id = Column(String, nullable=True, index=True)
    
    # Permissions
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    permissions = Column(JSON, default=list, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, is_active={self.is_active})>"