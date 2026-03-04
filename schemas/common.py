"""
Pydantic schemas for API request/response validation
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from models.application import AppStatus, AppType, ResourceStatus


# ============================================================
# Common Schemas
# ============================================================

class ResponseBase(BaseModel):
    """Base response schema"""
    code: int = Field(default=200, description="Response code")
    message: str = Field(default="success", description="Response message")


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Page size")


class PaginatedResponse(ResponseBase):
    """Paginated response schema"""
    total: int = Field(description="Total count")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Page size")


# ============================================================
# Application Schemas
# ============================================================

class ApplicationBase(BaseModel):
    """Base application schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(None, description="Application description")
    icon: Optional[str] = Field(None, max_length=100, description="Application icon")
    type: AppType = Field(default=AppType.CUSTOM, description="Application type")


class ApplicationCreate(ApplicationBase):
    """Create application schema"""
    schema: Optional[Dict[str, Any]] = Field(default={}, description="Application schema")


class ApplicationUpdate(BaseModel):
    """Update application schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    type: Optional[AppType] = None
    status: Optional[AppStatus] = None
    schema: Optional[Dict[str, Any]] = None


class ApplicationResponse(ApplicationBase):
    """Application response schema"""
    id: str
    status: AppStatus
    version: str
    schema: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ApplicationListResponse(PaginatedResponse):
    """Application list response"""
    data: List[ApplicationResponse]


# ============================================================
# Conversation Schemas
# ============================================================

class MessageCreate(BaseModel):
    """Create message schema"""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: Dict[str, Any] = Field(..., description="Message content (supports multimodal)")


class MessageResponse(BaseModel):
    """Message response schema"""
    id: str
    conversation_id: str
    role: str
    content: Dict[str, Any]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    """Create conversation schema"""
    title: str = Field(..., min_length=1, max_length=255)
    app_id: str


class ConversationResponse(BaseModel):
    """Conversation response schema"""
    id: str
    title: str
    app_id: str
    created_at: datetime
    updated_at: Optional[datetime]
    messages: List[MessageResponse] = []
    
    class Config:
        from_attributes = True


# ============================================================
# Resource Schemas
# ============================================================

class SkillBase(BaseModel):
    """Base skill schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: str


class SkillCreate(SkillBase):
    """Create skill schema"""
    config: Dict[str, Any] = Field(default={})


class SkillUpdate(BaseModel):
    """Update skill schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ResourceStatus] = None
    config: Optional[Dict[str, Any]] = None


class SkillResponse(SkillBase):
    """Skill response schema"""
    id: str
    status: ResourceStatus
    config: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class MCPServerBase(BaseModel):
    """Base MCP server schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: Optional[str] = None
    endpoint: Optional[str] = Field(None, max_length=500)


class MCPServerCreate(MCPServerBase):
    """Create MCP server schema"""
    config: Dict[str, Any] = Field(default={})


class MCPServerUpdate(BaseModel):
    """Update MCP server schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ResourceStatus] = None
    endpoint: Optional[str] = Field(None, max_length=500)
    config: Optional[Dict[str, Any]] = None


class MCPServerResponse(MCPServerBase):
    """MCP server response schema"""
    id: str
    status: ResourceStatus
    config: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================================
# WebSocket Schemas
# ============================================================

class WSMessage(BaseModel):
    """WebSocket message schema"""
    type: str = Field(..., description="Message type: chat, stream, tool_call, etc.")
    data: Dict[str, Any] = Field(default={}, description="Message payload")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Chat request via WebSocket"""
    message: str = Field(..., description="User message")
    app_id: str = Field(..., description="Application ID")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for continuing")
    stream: bool = Field(default=False, description="Whether to stream response")


class ChatResponse(BaseModel):
    """Chat response via WebSocket"""
    conversation_id: str
    message: MessageResponse
    status: str = Field(default="completed", description="Status: streaming, completed, error")


# ============================================================
# Agent Execution Schemas
# ============================================================

class AgentRunRequest(BaseModel):
    """Agent run request"""
    app_id: str
    input_data: Dict[str, Any] = Field(default={})
    conversation_id: Optional[str] = None
    stream: bool = Field(default=True)


class AgentRunResponse(ResponseBase):
    """Agent run response"""
    conversation_id: str
    output: Dict[str, Any]
    messages: List[MessageResponse]