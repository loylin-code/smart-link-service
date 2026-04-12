"""
Pydantic schemas for API request/response validation
Aligned with frontend expectations
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict

# Import enums from models
from models.application import AppStatus, AppType, ResourceStatus


# ============================================================
# Generic Type Variables
# ============================================================

T = TypeVar('T')


# ============================================================
# Common Response Schemas (Matching Frontend ApiResponse<T>)
# ============================================================

class ApiResponse(BaseModel, Generic[T]):
    """
    Unified API Response matching frontend expectations
    
    Frontend expects:
    interface ApiResponse<T> {
      code: number
      message: string
      data: T
      timestamp: number
    }
    """
    code: int = Field(default=200, description="Response code")
    message: str = Field(default="success", description="Response message")
    data: T
    timestamp: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp() * 1000))


class PaginatedData(BaseModel, Generic[T]):
    """
    Paginated data structure matching frontend expectations
    
    Frontend expects:
    interface PageResponse<T> {
      list: T[]
      total: number
      page: number
      pageSize: number
    }
    """
    list: List[T]
    total: int
    page: int
    page_size: int = Field(alias="pageSize", description="Page size (alias for compatibility)")
    
    class Config:
        populate_by_name = True


# ============================================================
# Pagination Parameters
# ============================================================

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, alias="pageSize", description="Page size")
    
    class Config:
        populate_by_name = True


# ============================================================
# Application Schemas
# ============================================================

class ApplicationBase(BaseModel):
    """Base application schema"""
    model_config = ConfigDict(protected_namespaces=())
    
    name: str = Field(..., min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(default="", description="Application description")
    icon: Optional[str] = Field(default="app", max_length=100, description="Application icon")
    type: AppType = Field(default=AppType.CUSTOM, description="Application type")


class ApplicationCreate(ApplicationBase):
    """Create application schema"""
    app_schema: Optional[Dict[str, Any]] = Field(default={}, alias="schema", description="Application schema (nodes and edges)")
    tags: Optional[List[str]] = Field(default=[], description="Application tags")


class ApplicationUpdate(BaseModel):
    """Update application schema"""
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=100)
    type: Optional[AppType] = None
    status: Optional[AppStatus] = None
    app_schema: Optional[Dict[str, Any]] = Field(None, alias="schema")
    tags: Optional[List[str]] = None


class ApplicationResponse(BaseModel):
    """Application response schema matching frontend Application type"""
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True, populate_by_name=True)
    
    id: str
    name: str
    description: str = ""
    icon: str = "app"
    type: AppType
    status: AppStatus
    version: str = "0.1.0"
    tags: List[str] = []
    app_schema: Dict[str, Any] = Field(default={}, alias="schema")
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    is_enabled: bool = False


class ApplicationListParams(PaginationParams):
    """Application list query parameters"""
    status: Optional[AppStatus] = None
    type: Optional[AppType] = None
    keyword: Optional[str] = None


class RunApplicationRequest(BaseModel):
    """Run application request"""
    input_data: Optional[Dict[str, Any]] = Field(default={})


class RunApplicationResponse(BaseModel):
    """Run application response"""
    conversation_id: str
    result: Dict[str, Any] = {}
    status: str = "completed"


# ============================================================
# Conversation Schemas
# ============================================================

class ConversationCreate(BaseModel):
    """Create conversation schema"""
    title: Optional[str] = Field(default="新对话", min_length=1, max_length=255)
    app_id: Optional[str] = None
    user_id: Optional[str] = None


class ConversationUpdate(BaseModel):
    """Update conversation schema"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = None


class ConversationListParams(PaginationParams):
    """Conversation list query parameters"""
    app_id: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[str] = None


class MessageResponse(BaseModel):
    """Message response schema"""
    id: str
    conversation_id: str
    role: str
    content: Any  # Can be string or object
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    components: List[Any] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation response schema matching frontend ChatConversation type"""
    id: str
    title: str
    app_id: Optional[str] = None
    user_id: Optional[str] = None
    status: str = "active"
    message_count: int = 0
    last_message_at: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: List[MessageResponse] = []
    
    class Config:
        from_attributes = True


class MessageListParams(BaseModel):
    """Message list query parameters"""
    limit: int = Field(default=50, ge=1, le=100)
    before_id: Optional[str] = None


class MessageCreate(BaseModel):
    """Create message schema"""
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: Any


# ============================================================
# Resource Schemas (Skills, MCP, Components)
# ============================================================

class SkillCreate(BaseModel):
    """Create skill schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    type: str = Field(default="custom", pattern="^(builtin|custom)$")
    config: Dict[str, Any] = Field(default={})


class SkillUpdate(BaseModel):
    """Update skill schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")
    config: Optional[Dict[str, Any]] = None


class SkillResponse(BaseModel):
    """Skill response schema matching frontend Skill type"""
    id: str
    name: str
    display_name: str = ""
    version: str = "1.0.0"
    category: str = "processing"
    status: str = "enabled"
    author: str = ""
    description: str = ""
    tags: List[str] = []
    risk_level: str = "low"
    requires_approval: bool = False
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    config: Dict[str, Any] = {}
    dependencies: Dict[str, Any] = {}
    stats: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SkillTestRequest(BaseModel):
    """Test skill request"""
    params: Dict[str, Any] = Field(default={})


class SkillTestResponse(BaseModel):
    """Test skill response"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class MCPServerCreate(BaseModel):
    """Create MCP server schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    type: Optional[str] = Field(default="stdio", pattern="^(stdio|sse|http)$")
    endpoint: Optional[str] = Field(None, max_length=500)
    config: Dict[str, Any] = Field(default={})


class MCPServerUpdate(BaseModel):
    """Update MCP server schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|connected|disconnected)$")
    endpoint: Optional[str] = Field(None, max_length=500)
    config: Optional[Dict[str, Any]] = None


class MCPServerResponse(BaseModel):
    """MCP server response schema matching frontend MCPServer type"""
    id: str
    name: str
    unique_id: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    homepage: Optional[str] = None
    transport: str = "stdio"
    status: str = "disconnected"
    response_time: Optional[int] = None
    error_count: int = 0
    capabilities: Dict[str, int] = {"tools": 0, "resources": 0, "prompts": 0}
    config: Dict[str, Any] = {}
    tools: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []
    last_active: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MCPServerTestResponse(BaseModel):
    """Test MCP server response"""
    success: bool
    response_time: Optional[int] = None
    error: Optional[str] = None


class MCPServerRefreshResponse(BaseModel):
    """Refresh MCP server capabilities response"""
    tools: int
    resources: int
    prompts: int


class ComponentResponse(BaseModel):
    """Component response schema"""
    id: str
    name: str
    description: str = ""
    type: str = ""
    status: str = "active"
    path: str = ""
    meta: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============================================================
# WebSocket Schemas
# ============================================================

class WSMessage(BaseModel):
    """WebSocket message schema matching frontend WSMessage"""
    type: str = Field(..., description="Message type: chat, stream, ping, pong, tool_call, status, error")
    data: Dict[str, Any] = Field(default={}, description="Message payload")
    timestamp: Optional[int] = Field(default_factory=lambda: int(datetime.utcnow().timestamp() * 1000))


class ChatRequest(BaseModel):
    """Chat request via WebSocket"""
    message: str = Field(..., description="User message")
    app_id: Optional[str] = Field(None, description="Application ID")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for continuing")
    attachments: Optional[List[Dict[str, Any]]] = None


class StreamResponseData(BaseModel):
    """Stream response data matching frontend StreamResponseData"""
    delta: str = ""
    done: bool = False
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    component: Optional[Any] = None


# ============================================================
# User & Auth Schemas
# ============================================================

class LoginRequest(BaseModel):
    """Login request"""
    email: str
    password: str


class RegisterRequest(BaseModel):
    """Register request"""
    email: str
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class UserResponse(BaseModel):
    """User response"""
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    tenant_id: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True