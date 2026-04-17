"""
Plugin marketplace models
"""
import enum
from sqlalchemy import (
    Column, String, Text, JSON, DateTime, Integer, 
    Boolean, Enum as SQLEnum, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.session import Base
from models.application import generate_uuid


class PluginStatus(str, enum.Enum):
    """Plugin status enum"""
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"


class Plugin(Base):
    """Plugin marketplace model"""
    __tablename__ = "plugins"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    
    # Plugin metadata
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(20), nullable=False)
    author = Column(String(255), nullable=True)
    license = Column(String(50), nullable=True)
    tags = Column(JSON, default=list, nullable=False)
    icon = Column(String(500), nullable=True)
    
    # Plugin package
    package_name = Column(String(255), nullable=False)
    package_version = Column(String(20), nullable=False)
    entry_point = Column(String(255), nullable=False)
    
    # Status
    status = Column(SQLEnum(PluginStatus), default=PluginStatus.PUBLISHED, nullable=False)
    
    # Statistics
    install_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    installations = relationship("PluginInstallation", back_populates="plugin")
    
    # Indexes
    __table_args__ = (
        Index('ix_plugins_name_status', 'name', 'status'),
    )
    
    def __repr__(self):
        return f"<Plugin(id={self.id}, name={self.name}, version={self.version})>"


class PluginInstallation(Base):
    """Plugin installation record"""
    __tablename__ = "plugin_installations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=False, index=True)
    
    # Installation settings
    settings = Column(JSON, default=dict, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    installed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    plugin = relationship("Plugin", back_populates="installations")
    
    # Indexes
    __table_args__ = (
        Index('ix_plugin_installations_tenant_plugin', 'tenant_id', 'plugin_id'),
    )
    
    def __repr__(self):
        return f"<PluginInstallation(id={self.id}, plugin_id={self.plugin_id})>"