"""Plugin marketplace request/response schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class PluginCreate(BaseModel):
    """Publish plugin request."""
    name: str = Field(..., description="Plugin name")
    description: Optional[str] = Field(None, description="Plugin description")
    version: str = Field("1.0.0", description="Plugin version")
    author: Optional[str] = Field(None, description="Author name")
    license: Optional[str] = Field("MIT", description="License type")
    tags: List[str] = Field(default_factory=list, description="Category tags")
    icon: Optional[str] = Field(None, description="Icon URL")
    package_name: str = Field(..., description="Python package name")
    package_version: str = Field(..., description="Package version")
    entry_point: str = Field(..., description="Entry point: module:ClassName")


class PluginUpdate(BaseModel):
    """Update plugin request."""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    tags: Optional[List[str]] = None
    icon: Optional[str] = None
    status: Optional[str] = None


class PluginResponse(BaseModel):
    """Plugin response."""
    id: str
    tenant_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    version: str
    author: Optional[str] = None
    license: Optional[str] = None
    tags: List[str] = []
    icon: Optional[str] = None
    status: str
    install_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


class PluginInstallRequest(BaseModel):
    """Install plugin request."""
    settings: Dict[str, Any] = Field(default_factory=dict, description="Plugin settings")
    enabled: bool = Field(True, description="Enable after installation")


class PluginInstallationResponse(BaseModel):
    """Plugin installation response."""
    id: str
    tenant_id: str
    plugin_id: str
    plugin_name: str
    enabled: bool
    settings: Dict[str, Any] = {}
    installed_at: datetime


class PluginListResponse(BaseModel):
    """Plugin list response."""
    data: List[PluginResponse]
    total: int