"""
Agent (Role) model for SmartLink
Based on architecture design document Role model
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, JSON, DateTime, Integer, 
    Boolean, Enum as SQLEnum, ForeignKey, Index
)
from sqlalchemy.orm import relationship
import enum
import uuid

from db.session import Base
from core.time_utils import now_utc8


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class AgentStatus(str, enum.Enum):
    """Agent status enum matching frontend AgentStatus"""
    DRAFT = "draft"          # 草稿
    ACTIVE = "active"        # 激活可用
    PAUSED = "paused"        # 暂停
    DEPRECATED = "deprecated"  # 废弃


class AgentType(str, enum.Enum):
    """Agent type enum matching frontend AgentType"""
    SYSTEM = "system"        # 系统预置角色
    CUSTOM = "custom"        # 用户自定义角色
    TEMPLATE = "template"    # 模板角色（可复制）


class Agent(Base):
    """
    Agent (Role) model - 核心智能体定义
    
    Based on architecture design:
    - identity: 身份定义
    - capabilities: 能力定义
    - knowledge: 知识库 (RAG)
    - pageSchema: 页面设计 Schema
    """
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # === 基础信息 ===
    type = Column(SQLEnum(AgentType), default=AgentType.CUSTOM, nullable=False)
    status = Column(SQLEnum(AgentStatus), default=AgentStatus.DRAFT, nullable=False)
    version = Column(String(20), default="0.1.0", nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    
    # === 身份定义 (identity) ===
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=False, unique=True, index=True)  # 唯一标识码（路由键）
    avatar = Column(String(500), nullable=True)  # 头像 URL
    description = Column(Text, nullable=True)
    persona = Column(Text, nullable=True)  # 系统提示词
    welcome_message = Column(Text, nullable=True)  # 欢迎语
    responsibilities = Column(JSON, default=list, nullable=False)  # 职责清单
    
    # === 能力定义 (capabilities) ===
    mcp_servers = Column(JSON, default=list, nullable=False)  # MCP 服务绑定
    skills = Column(JSON, default=list, nullable=False)  # Skills 绑定
    tools = Column(JSON, default=list, nullable=False)  # Tools 绑定
    llm_config = Column(JSON, default=dict, nullable=False)  # LLM 配置
    
    # === 知识库 (knowledge) ===
    documents = Column(JSON, default=list, nullable=False)  # 文档源
    databases = Column(JSON, default=list, nullable=False)  # 数据库连接
    apis = Column(JSON, default=list, nullable=False)  # API 数据源
    search_config = Column(JSON, default=dict, nullable=False)  # 检索配置
    
    # === 页面设计 Schema ===
    page_schema = Column(JSON, default=dict, nullable=True)
    
    # === 元数据 ===
    creator = Column(String, ForeignKey("users.id"), nullable=True)
    category = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=now_utc8, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="agents")
    
    # Indexes
    __table_args__ = (
        Index('ix_agents_tenant_status', 'tenant_id', 'status'),
        Index('ix_agents_tenant_type', 'tenant_id', 'type'),
        Index('ix_agents_tenant_code', 'tenant_id', 'code', unique=True),
    )
    
    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary matching frontend Agent interface"""
        return {
            "id": self.id,
            "type": self.type.value if self.type else AgentType.CUSTOM.value,
            "status": self.status.value if self.status else AgentStatus.DRAFT.value,
            "version": self.version or "0.1.0",
            "tags": self.tags or [],
            "createdAt": int(self.created_at.timestamp() * 1000) if self.created_at else 0,
            "updatedAt": int(self.updated_at.timestamp() * 1000) if self.updated_at else 0,
            "creator": self.creator,
            "category": self.category,
            "pageSchema": self.page_schema,
            "identity": {
                "name": self.name,
                "code": self.code,
                "avatar": self.avatar or "",
                "description": self.description or "",
                "persona": self.persona or "",
                "welcomeMessage": self.welcome_message or "",
                "responsibilities": self.responsibilities or []
            },
            "capabilities": {
                "mcpServers": self.mcp_servers or [],
                "skills": self.skills or [],
                "tools": self.tools or [],
                "llm": self.llm_config or {
                    "provider": "openai",
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "maxTokens": 4096,
                    "topP": 1
                }
            },
            "knowledge": {
                "documents": self.documents or [],
                "databases": self.databases or [],
                "apis": self.apis or [],
                "searchConfig": self.search_config or {
                    "enabled": False,
                    "topK": 10,
                    "similarityThreshold": 0.7,
                    "rerankEnabled": False
                }
            }
        }


class AgentRuntimeStatus(Base):
    """
    Agent runtime status tracking
    """
    __tablename__ = "agent_runtime_status"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Runtime state
    status = Column(String(50), default="idle", nullable=False)  # idle, busy, error
    session_count = Column(Integer, default=0, nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    
    # Resource usage
    tokens_consumed = Column(Integer, default=0, nullable=False)
    avg_latency = Column(Integer, default=0, nullable=False)  # milliseconds
    
    # Error tracking
    error_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=now_utc8, nullable=True)
    
    # Relationships
    agent = relationship("Agent")
    
    def __repr__(self):
        return f"<AgentRuntimeStatus(agent_id={self.agent_id}, status={self.status})>"