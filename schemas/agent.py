"""
Agent schemas matching frontend types
Based on app/src/types/index.ts Agent interface
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from models.agent import AgentStatus, AgentType


# ============================================================
# Identity Schemas
# ============================================================

class AgentResponsibility(BaseModel):
    """职责定义"""
    id: str
    name: str
    description: str
    priority: int = 0
    keywords: List[str] = []
    examples: List[str] = []


class AgentIdentity(BaseModel):
    """身份定义"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    avatar: str = ""
    description: str = ""
    persona: str = ""
    welcome_message: str = Field(default="", alias="welcomeMessage")
    responsibilities: List[AgentResponsibility] = []


# ============================================================
# Capabilities Schemas
# ============================================================

class MCPServerBinding(BaseModel):
    """MCP 服务绑定"""
    model_config = ConfigDict(populate_by_name=True)
    
    server_id: str = Field(..., alias="serverId")
    required: bool = True
    fallback_action: str = Field(default="skip", alias="fallbackAction")  # skip, error, wait
    custom_config: Optional[Dict[str, Any]] = Field(default=None, alias="customConfig")


class SkillBinding(BaseModel):
    """Skill 绑定"""
    model_config = ConfigDict(populate_by_name=True)
    
    skill_id: str = Field(..., alias="skillId")
    version: str = "1.0.0"
    enabled: bool = True
    parameters: Dict[str, Any] = {}


class ToolBinding(BaseModel):
    """Tool 绑定"""
    model_config = ConfigDict(populate_by_name=True)
    
    tool_id: str = Field(..., alias="toolId")
    enabled: bool = True
    parameters: Optional[Dict[str, Any]] = None


class AgentLLMConfig(BaseModel):
    """LLM 配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, alias="maxTokens")
    top_p: float = Field(default=1, ge=0, le=1)
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")


class AgentCapabilities(BaseModel):
    """能力定义"""
    model_config = ConfigDict(populate_by_name=True)
    
    mcp_servers: List[MCPServerBinding] = Field(default=[], alias="mcpServers")
    skills: List[SkillBinding] = []
    tools: List[ToolBinding] = []
    llm: AgentLLMConfig = Field(default_factory=AgentLLMConfig)


# ============================================================
# Knowledge Schemas
# ============================================================

class DocumentSource(BaseModel):
    """文档源"""
    id: str
    name: str
    type: str  # file, url, text
    source: str
    enabled: bool = True


class DatabaseSource(BaseModel):
    """数据库源"""
    id: str
    name: str
    type: str  # mysql, postgresql, mongodb, redis
    connection_string: str
    enabled: bool = True


class APISource(BaseModel):
    """API 数据源"""
    id: str
    name: str
    endpoint: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True


class SearchConfig(BaseModel):
    """检索配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    enabled: bool = False
    top_k: int = Field(default=10, alias="topK")
    similarity_threshold: float = Field(default=0.7, alias="similarityThreshold")
    rerank_enabled: bool = Field(default=False, alias="rerankEnabled")


class AgentKnowledge(BaseModel):
    """知识库配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    documents: List[DocumentSource] = []
    databases: List[DatabaseSource] = []
    apis: List[APISource] = []
    search_config: SearchConfig = Field(default_factory=SearchConfig, alias="searchConfig")


# ============================================================
# Agent CRUD Schemas
# ============================================================

class AgentCreate(BaseModel):
    """创建智能体"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""
    avatar: Optional[str] = None
    persona: Optional[str] = ""
    welcome_message: Optional[str] = Field(default="", alias="welcomeMessage")
    tags: List[str] = []
    category: Optional[str] = None


class AgentUpdate(BaseModel):
    """更新智能体"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    avatar: Optional[str] = None
    persona: Optional[str] = None
    welcome_message: Optional[str] = Field(None, alias="welcomeMessage")
    identity: Optional[AgentIdentity] = None
    capabilities: Optional[AgentCapabilities] = None
    knowledge: Optional[AgentKnowledge] = None
    page_schema: Optional[Dict[str, Any]] = Field(None, alias="pageSchema")
    tags: Optional[List[str]] = None
    status: Optional[AgentStatus] = None


class AgentListParams(BaseModel):
    """智能体列表查询参数"""
    model_config = ConfigDict(populate_by_name=True)
    
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100, alias="pageSize")
    status: Optional[AgentStatus] = None
    type: Optional[AgentType] = None
    keyword: Optional[str] = None
    category: Optional[str] = None


# ============================================================
# Agent Response Schemas
# ============================================================

class AgentResponse(BaseModel):
    """智能体响应 - 匹配前端 Agent 接口"""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    
    id: str
    type: AgentType = AgentType.CUSTOM
    status: AgentStatus = AgentStatus.DRAFT
    
    # 身份定义
    identity: AgentIdentity
    
    # 能力定义
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    
    # 知识库
    knowledge: AgentKnowledge = Field(default_factory=AgentKnowledge)
    
    # 页面设计 Schema
    page_schema: Optional[Dict[str, Any]] = Field(default=None, alias="pageSchema")
    
    # 元数据
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    tags: List[str] = []
    version: str = "0.1.0"
    creator: Optional[str] = None
    category: Optional[str] = None


class AgentRuntimeStatusResponse(BaseModel):
    """智能体运行时状态"""
    model_config = ConfigDict(populate_by_name=True)
    
    agent_id: str = Field(alias="agentId")
    status: str = "idle"  # idle, busy, error
    session_count: int = Field(default=0, alias="sessionCount")
    last_active_at: Optional[int] = Field(default=None, alias="lastActiveAt")
    tokens_consumed: int = Field(default=0, alias="tokensConsumed")
    avg_latency: int = Field(default=0, alias="avgLatency")


# ============================================================
# Helper functions
# ============================================================

def agent_to_response(agent) -> AgentResponse:
    """
    Convert Agent model to response schema
    
    Args:
        agent: Agent SQLAlchemy model instance
        
    Returns:
        AgentResponse matching frontend expectations
    """
    return AgentResponse(
        id=agent.id,
        type=agent.type,
        status=agent.status,
        identity=AgentIdentity(
            name=agent.name,
            code=agent.code,
            avatar=agent.avatar or "",
            description=agent.description or "",
            persona=agent.persona or "",
            welcome_message=agent.welcome_message or "",
            responsibilities=agent.responsibilities or []
        ),
        capabilities=AgentCapabilities(
            mcp_servers=agent.mcp_servers or [],
            skills=agent.skills or [],
            tools=agent.tools or [],
            llm=agent.llm_config or AgentLLMConfig()
        ),
        knowledge=AgentKnowledge(
            documents=agent.documents or [],
            databases=agent.databases or [],
            apis=agent.apis or [],
            search_config=agent.search_config or SearchConfig()
        ),
        page_schema=agent.page_schema,
        created_at=int(agent.created_at.timestamp() * 1000) if agent.created_at else 0,
        updated_at=int(agent.updated_at.timestamp() * 1000) if agent.updated_at else 0,
        tags=agent.tags or [],
        version=agent.version or "0.1.0",
        creator=agent.creator,
        category=agent.category
    )