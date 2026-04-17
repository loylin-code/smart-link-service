"""MCP Server request/response schemas."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class MCPServerBase(BaseModel):
    """Base MCP server schema."""
    name: str = Field(..., description="Server name")
    description: Optional[str] = Field(None, description="Server description")
    type: str = Field(..., description="Transport type: 'sse' or 'http'")
    endpoint: str = Field(..., description="Server endpoint URL")
    config: Dict[str, Any] = Field(default_factory=dict, description="Server config (headers, timeout)")


class MCPServerCreate(MCPServerBase):
    """Create MCP server request."""
    pass


class MCPServerUpdate(BaseModel):
    """Update MCP server request."""
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    endpoint: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class MCPServerResponse(BaseModel):
    """MCP server response."""
    id: str
    tenant_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    type: str
    endpoint: str
    config: Dict[str, Any] = {}
    status: str
    tools: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []  # MCP Prompts
    last_connected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class MCPToolResponse(BaseModel):
    """MCP tool response."""
    name: str
    description: str
    input_schema: Dict[str, Any] = {}


class MCPConnectResult(BaseModel):
    """MCP connection test result."""
    connected: bool
    tools: Optional[int] = None
    error: Optional[str] = None


class MCPServerTestResponse(BaseModel):
    """MCP server test response."""
    success: bool
    response_time: int
    error: Optional[str] = None


class MCPServerRefreshResponse(BaseModel):
    """MCP server refresh response."""
    tools: int
    resources: int
    prompts: int = 0
