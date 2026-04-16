"""BaseSubAgent abstract class for role-based execution"""
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class SubAgentCapability(BaseModel):
    """SubAgent能力定义"""
    name: str
    description: str
    required_tools: List[str] = Field(default_factory=list)
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)


class SubAgentResult(BaseModel):
    """SubAgent执行结果"""
    success: bool
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time: float = 0.0
    error: Optional[str] = None


class BaseSubAgent(ABC):
    """SubAgent抽象基类
    
    所有SubAgent必须继承此类并实现execute方法
    """
    
    # 类属性 - 子类必须定义
    role: str = ""
    description: str = ""
    capabilities: List[SubAgentCapability] = []
    
    def __init__(
        self,
        llm_client: Any,
        toolkit: Any,
        memory_manager: Any
    ):
        """初始化SubAgent
        
        Args:
            llm_client: LLM客户端
            toolkit: AgentToolkit (Skills + MCP)
            memory_manager: 记忆管理器
        """
        self.llm = llm_client
        self.toolkit = toolkit
        self.memory = memory_manager
        self.id = f"{self.role}_{uuid.uuid4().hex[:8]}"
    
    @abstractmethod
    async def execute(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """执行分配的任务
        
        Args:
            task: Task对象
            context: 执行上下文
            
        Returns:
            SubAgentResult: 执行结果
        """
        pass
    
    def get_capabilities(self) -> List[SubAgentCapability]:
        """获取能力清单"""
        return self.capabilities
    
    def can_handle(self, intent_type: str) -> bool:
        """检查是否能处理某意图类型"""
        return any(cap.name == intent_type for cap in self.capabilities)
    
    async def _prepare_context(self, conversation_id: str) -> List[Dict]:
        """准备上下文记忆"""
        if self.memory and conversation_id:
            return await self.memory.get_context_window(conversation_id)
        return []
    
    async def _execute_llm(
        self,
        prompt: str,
        tools: List[Dict] = None
    ) -> str:
        """执行LLM调用"""
        if tools and hasattr(self.llm, 'chat_with_tools'):
            return await self.llm.chat_with_tools(prompt, tools)
        elif hasattr(self.llm, 'chat'):
            return await self.llm.chat(prompt)
        else:
            raise NotImplementedError("LLM client missing chat method")
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(role={self.role}, id={self.id})>"