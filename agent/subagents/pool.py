"""SubAgentPool - Manager for role-based agents"""
from typing import Dict, List, Optional, Any

from agent.subagents.base import BaseSubAgent, SubAgentResult
from agent.subagents.research import ResearchAgent
from agent.subagents.code import CodeAgent
from agent.subagents.data import DataAgent
from agent.subagents.doc import DocAgent


class SubAgentPool:
    """SubAgent池管理器
    
    管理所有内置SubAgent并提供任务分派能力
    """
    
    def __init__(
        self,
        llm_client: Any,
        toolkit: Any,
        memory_manager: Any
    ):
        """初始化SubAgent Pool
        
        Args:
            llm_client: LLM客户端
            toolkit: AgentToolkit
            memory_manager: 记忆管理器
        """
        self.llm = llm_client
        self.toolkit = toolkit
        self.memory = memory_manager
        
        # Agent池
        self._agents: Dict[str, BaseSubAgent] = {}
        self._initialize_agents()
    
    def _initialize_agents(self):
        """初始化内置SubAgent"""
        agent_classes = [ResearchAgent, CodeAgent, DataAgent, DocAgent]
        
        for agent_class in agent_classes:
            agent = agent_class(self.llm, self.toolkit, self.memory)
            self._agents[agent.role] = agent
    
    def get_agent(self, role: str) -> Optional[BaseSubAgent]:
        """获取指定角色的SubAgent
        
        Args:
            role: SubAgent角色
            
        Returns:
            SubAgent实例或None
        """
        return self._agents.get(role)
    
    def get_available_roles(self) -> List[str]:
        """获取可用角色列表
        
        Returns:
            角色名称列表
        """
        return list(self._agents.keys())
    
    def get_agent_capabilities(self, role: str) -> List[Dict]:
        """获取指定角色的能力清单
        
        Args:
            role: SubAgent角色
            
        Returns:
            能力字典列表
        """
        agent = self.get_agent(role)
        if agent:
            return [cap.model_dump() for cap in agent.get_capabilities()]
        return []
    
    def register_custom_agent(self, agent: BaseSubAgent):
        """注册自定义SubAgent
        
        Args:
            agent: BaseSubAgent实例
        """
        self._agents[agent.role] = agent
    
    async def execute_task(
        self,
        role: str,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """分派任务给指定SubAgent执行
        
        Args:
            role: SubAgent角色
            task: Task对象
            context: 执行上下文
            
        Returns:
            SubAgentResult: 执行结果
            
        Raises:
            ValueError: SubAgent不存在
        """
        agent = self.get_agent(role)
        if not agent:
            raise ValueError(f"SubAgent '{role}' not found")
        
        return await agent.execute(task, context)
    
    def __repr__(self):
        return f"<SubAgentPool(roles={self.get_available_roles()})>"