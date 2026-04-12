"""
Multi-tenant models for SmartLink
Includes Tenant, User, and related models
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, JSON, DateTime, Integer, 
    Boolean, Enum as SQLEnum, ForeignKey, Index, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class TenantStatus(str, enum.Enum):
    """Tenant status enum"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CHURNED = "churned"


class BillingPlan(str, enum.Enum):
    """Billing plan enum"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserRole(str, enum.Enum):
    """User role enum"""
    OWNER = "owner"           # Full access including billing
    ADMIN = "admin"           # Manage resources, users
    DEVELOPER = "developer"   # Create/edit applications
    VIEWER = "viewer"         # Read-only access
    SERVICE = "service"       # API-only access


class Tenant(Base):
    """
    Tenant model for multi-tenancy
    Each tenant represents an organization/company
    """
    __tablename__ = "tenants"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(TenantStatus), default=TenantStatus.ACTIVE, nullable=False)
    
    # Billing
    billing_plan = Column(SQLEnum(BillingPlan), default=BillingPlan.FREE, nullable=False)
    billing_email = Column(String(255), nullable=True)
    
    # Resource quotas
    max_sessions = Column(Integer, default=10, nullable=False)
    max_agents = Column(Integer, default=2, nullable=False)
    max_users = Column(Integer, default=5, nullable=False)
    monthly_token_limit = Column(Integer, default=100000, nullable=False)
    monthly_request_limit = Column(Integer, default=1000, nullable=False)
    
    # Current usage (reset monthly)
    current_tokens_used = Column(Integer, default=0, nullable=False)
    current_requests_used = Column(Integer, default=0, nullable=False)
    
    # Settings (JSON for flexibility)
    settings = Column(JSON, default=dict, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="tenant", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="tenant", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="tenant", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_tenants_status_plan', 'status', 'billing_plan'),
    )
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, status={self.status})>"
    
    def is_active(self) -> bool:
        """Check if tenant is active"""
        return self.status == TenantStatus.ACTIVE
    
    def check_quota(self, resource: str, amount: int = 1) -> bool:
        """
        Check if tenant has quota available
        
        Args:
            resource: Resource type (sessions, agents, users, tokens, requests)
            amount: Amount to check
            
        Returns:
            True if quota available
        """
        quota_map = {
            "sessions": (self.max_sessions, None),
            "agents": (self.max_agents, None),
            "users": (self.max_users, None),
            "tokens": (self.monthly_token_limit, self.current_tokens_used),
            "requests": (self.monthly_request_limit, self.current_requests_used),
        }
        
        if resource not in quota_map:
            return False
        
        limit, used = quota_map[resource]
        if used is None:
            return True  # No usage tracking for this resource
        return used + amount <= limit


class User(Base):
    """
    User model with OAuth support
    Users belong to a tenant and have roles
    """
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Profile
    email = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Role and status
    role = Column(SQLEnum(UserRole), default=UserRole.DEVELOPER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # OAuth fields
    oauth_provider = Column(String(50), nullable=True)  # google, github, gitlab, etc.
    oauth_id = Column(String(255), nullable=True)  # Provider-specific user ID
    oauth_token = Column(Text, nullable=True)  # Encrypted OAuth token
    oauth_refresh_token = Column(Text, nullable=True)  # Encrypted refresh token
    
    # Session tracking
    last_login = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    
    # Preferences
    preferences = Column(JSON, default=dict, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    conversations = relationship("Conversation", back_populates="user")
    messages = relationship("Message", back_populates="user")
    
    # Indexes
    __table_args__ = (
        Index('ix_users_tenant_email', 'tenant_id', 'email', unique=True),
        Index('ix_users_oauth', 'oauth_provider', 'oauth_id'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if user has a specific permission based on role
        
        Args:
            permission: Permission string (e.g., 'app:create', 'user:delete')
            
        Returns:
            True if user has permission
        """
        # Define permission matrix by role
        permissions = {
            UserRole.OWNER: [
                "tenant:read", "tenant:update", "tenant:delete",
                "user:create", "user:read", "user:update", "user:delete",
                "app:create", "app:read", "app:update", "app:delete", "app:execute",
                "conversation:create", "conversation:read", "conversation:delete",
                "resource:create", "resource:read", "resource:delete",
                "api_key:create", "api_key:read", "api_key:delete",
                "billing:read", "billing:update",
            ],
            UserRole.ADMIN: [
                "user:create", "user:read", "user:update",
                "app:create", "app:read", "app:update", "app:delete", "app:execute",
                "conversation:create", "conversation:read", "conversation:delete",
                "resource:create", "resource:read", "resource:delete",
                "api_key:create", "api_key:read", "api_key:delete",
            ],
            UserRole.DEVELOPER: [
                "app:create", "app:read", "app:update", "app:execute",
                "conversation:create", "conversation:read",
                "resource:create", "resource:read",
            ],
            UserRole.VIEWER: [
                "app:read",
                "conversation:read",
                "resource:read",
            ],
            UserRole.SERVICE: [
                "app:read", "app:execute",
                "conversation:create", "conversation:read",
            ],
        }
        
        return permission in permissions.get(self.role, [])


class TenantSettings(Base):
    """
    Tenant-specific settings
    Stores configurable options per tenant
    """
    __tablename__ = "tenant_settings"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # LLM settings
    default_llm_provider = Column(String(50), default="openai", nullable=False)
    default_llm_model = Column(String(100), default="gpt-4o-mini", nullable=False)
    
    # Feature flags
    enable_web_search = Column(Boolean, default=False, nullable=False)
    enable_file_upload = Column(Boolean, default=True, nullable=False)
    enable_mcp = Column(Boolean, default=False, nullable=False)
    
    # Rate limiting
    rate_limit_requests_per_minute = Column(Integer, default=60, nullable=False)
    rate_limit_tokens_per_day = Column(Integer, default=100000, nullable=False)
    
    # Custom branding
    branding_logo_url = Column(String(500), nullable=True)
    branding_primary_color = Column(String(20), nullable=True)
    branding_custom_css = Column(Text, nullable=True)
    
    # Webhook settings
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<TenantSettings(tenant_id={self.tenant_id})>"