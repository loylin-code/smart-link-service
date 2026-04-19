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
import uuid

from db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


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


class SkillDomain(str, enum.Enum):
    """Skill domain enum"""
    RESOURCE = "resource"
    CONVERSATION = "conversation"
    APPLICATION = "application"


class SkillVisibility(str, enum.Enum):
    """Skill visibility enum"""
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class Application(Base):
    """
    Application model with multi-tenant support
    """
    __tablename__ = "applications"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Application info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    type = Column(SQLEnum(AppType), default=AppType.CUSTOM, nullable=False)
    status = Column(SQLEnum(AppStatus), default=AppStatus.DRAFT, nullable=False)
    version = Column(String(20), default="0.1.0", nullable=False)
    
    # Application flow schema (nodes and edges)
    schema = Column(JSON, default=dict, nullable=False)
    
    # LLM settings
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    llm_temperature = Column(String(10), default="0.7", nullable=True)
    
    # Skills and tools
    skills = Column(JSON, default=list, nullable=False)  # List of skill names
    tools = Column(JSON, default=list, nullable=False)  # List of tool configs
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="applications")
    conversations = relationship("Conversation", back_populates="application", cascade="all, delete-orphan")
    resources = relationship("Resource", back_populates="application", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_applications_tenant_status', 'tenant_id', 'status'),
        Index('ix_applications_tenant_type', 'tenant_id', 'type'),
    )
    
    def __repr__(self):
        return f"<Application(id={self.id}, name={self.name}, status={self.status})>"


class Conversation(Base):
    """
    Conversation model with multi-tenant support
    """
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    app_id = Column(String, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Conversation info
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)  # AI-generated summary
    
    # Context
    context = Column(JSON, default=dict, nullable=False)  # Conversation context/state
    extra_metadata = Column("metadata", JSON, default=dict, nullable=False)  # Additional metadata
    
    # Status
    is_archived = Column(Boolean, default=False, nullable=False)
    is_starred = Column(Boolean, default=False, nullable=False)
    
    # Token usage
    total_tokens = Column(Integer, default=0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_conversations_tenant_user', 'tenant_id', 'user_id'),
        Index('ix_conversations_tenant_archived', 'tenant_id', 'is_archived'),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title})>"


class Message(Base):
    """
    Message model with multi-tenant support
    """
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Message content
    role = Column(String(50), nullable=False)  # user, assistant, system, tool
    content = Column(JSON, nullable=False)  # Support multimodal content
    sequence_number = Column(Integer, nullable=False)  # Order in conversation
    
    # Tool calls
    tool_calls = Column(JSON, nullable=True)  # Tool call requests
    tool_call_id = Column(String(100), nullable=True)  # If this is a tool response
    
    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Metadata
    extra_metadata = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('ix_messages_conversation_seq', 'conversation_id', 'sequence_number'),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"


class Resource(Base):
    """
    Resource model for files and documents with multi-tenant support
    """
    __tablename__ = "resources"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    app_id = Column(String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Resource info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=False)  # file, document, image, etc.
    mime_type = Column(String(100), nullable=True)
    
    # Storage
    storage_path = Column(String(500), nullable=False)  # Path in object storage
    size_bytes = Column(Integer, default=0, nullable=False)
    checksum = Column(String(64), nullable=True)  # SHA-256 checksum
    
    # Versioning
    version = Column(Integer, default=1, nullable=False)
    
    # Processing status
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    processing_error = Column(Text, nullable=True)
    
    # Metadata
    extra_metadata = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="resources")
    versions = relationship("ResourceVersion", back_populates="resource", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_resources_tenant_type', 'tenant_id', 'type'),
    )
    
    def __repr__(self):
        return f"<Resource(id={self.id}, name={self.name}, type={self.type})>"


class ResourceVersion(Base):
    """
    Resource version model for version history
    """
    __tablename__ = "resource_versions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    resource_id = Column(String, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Version info
    version_number = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, default=0, nullable=False)
    checksum = Column(String(64), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    resource = relationship("Resource", back_populates="versions")
    
    # Indexes
    __table_args__ = (
        Index('ix_resource_versions_resource_version', 'resource_id', 'version_number', unique=True),
    )
    
    def __repr__(self):
        return f"<ResourceVersion(id={self.id}, version={self.version_number})>"


class Skill(Base):
    """
    Skill model with multi-tenant support
    """
    __tablename__ = "skills"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL for builtin
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=False)  # builtin, custom
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # Skill configuration
    config = Column(JSON, default=dict, nullable=False)
    parameters_schema = Column(JSON, default=dict, nullable=False)  # JSON Schema for parameters
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_skills_tenant_name', 'tenant_id', 'name', unique=True),
    )
    
    def __repr__(self):
        return f"<Skill(id={self.id}, name={self.name}, type={self.type})>"


class MCPServer(Base):
    """
    MCP Server model with multi-tenant support
    """
    __tablename__ = "mcp_servers"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=True)  # stdio, sse, etc.
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # MCP Server configuration
    endpoint = Column(String(500), nullable=True)  # URL or command
    config = Column(JSON, default=dict, nullable=False)  # args, env, etc.
    
    # Capabilities
    tools = Column(JSON, default=list, nullable=False)  # Available tools
    resources = Column(JSON, default=list, nullable=False)  # Available resources
    prompts = Column(JSON, default=list, nullable=False)  # Available prompts
    
    # Status tracking
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_mcp_servers_tenant_name', 'tenant_id', 'name', unique=True),
    )
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name={self.name})>"


class Component(Base):
    """
    Frontend component metadata model
    """
    __tablename__ = "components"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=False)
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # Component metadata
    path = Column(String(500), nullable=False)  # Component file path
    meta = Column(JSON, default=dict, nullable=False)  # Props, events, slots
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_components_tenant_name', 'tenant_id', 'name', unique=True),
    )
    
    def __repr__(self):
        return f"<Component(id={self.id}, name={self.name})>"


class APIKey(Base):
    """
    API Key model with multi-tenant support
    """
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Key info
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # Hashed key
    key_prefix = Column(String(10), nullable=False)  # First few chars for identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Permissions
    is_active = Column(Boolean, default=True, nullable=False)
    scopes = Column(JSON, default=list, nullable=False)  # List of scope strings
    rate_limit = Column(Integer, default=60, nullable=False)  # Requests per minute
    
    # Usage tracking
    total_requests = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_ip = Column(String(45), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="api_keys")
    
    # Indexes
    __table_args__ = (
        Index('ix_api_keys_tenant_active', 'tenant_id', 'is_active'),
    )
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, is_active={self.is_active})>"


class AuditLog(Base):
    """
    Audit log model for tracking important actions
    """
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Action info
    action = Column(String(100), nullable=False, index=True)  # e.g., "app.create", "user.login"
    resource_type = Column(String(100), nullable=False)  # e.g., "application", "user"
    resource_id = Column(String, nullable=True)
    
    # Details
    details = Column(JSON, default=dict, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Result
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action})>"