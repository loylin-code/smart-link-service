"""
AgentScope-based Orchestrator
Replaces original orchestrator with AgentScope integration
"""
from typing import Dict, Any, Optional, AsyncIterator, List
from datetime import datetime

from agent.agentscope.hub import AgentHub
from agent.agentscope.agent_factory import AgentFactory
from agent.agentscope.toolkit import AgentToolkit
from agent.core.context import AgentContext
from core.exceptions import AgentError
from db.session import async_session_maker


class AgentOrchestrator:
    """AgentScope-based Agent Orchestrator
    
    Manages agent execution using AgentScope framework components:
    - AgentHub: Central message coordination for multi-agent conversations
    - AgentFactory: Creates and configures AgentScope agents
    - AgentToolkit: Registers and manages Skills and MCP tools
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize orchestrator with AgentScope components
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.hub = AgentHub.get_instance()
        self.factory = AgentFactory()
        self.context = AgentContext()
        self.is_executing = False
    
    async def execute(
        self,
        agent_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute agent task
        
        Args:
            agent_id: Agent ID to execute
            input_data: Input data containing message and optional parameters
            conversation_id: Optional conversation ID for context
            
        Returns:
            Execution result dictionary
            
        Raises:
            AgentError: If execution fails
        """
        self.is_executing = True
        try:
            # Load agent configuration from database
            role_config = await self._load_agent_config(agent_id)
            
            # Initialize context
            self.context.init(role_config, input_data, conversation_id)
            
            # Create toolkit with skills
            toolkit = await self._create_toolkit(role_config)
            
            # Build system prompt from identity
            identity = role_config.get("identity", {})
            sys_prompt = self.factory._build_sys_prompt(identity, {})
            
            # Get LLM config
            capabilities = role_config.get("capabilities", {})
            llm_config = capabilities.get("llm", {})
            model_name = llm_config.get("model", "gpt-4")
            
            # Create agent
            agent = await self.factory.create_agent(
                model_name=model_name,
                sys_prompt=sys_prompt,
                tools=toolkit.get_tool_schemas() if toolkit.get_tool_schemas() else None
            )
            
            # Execute agent
            message = {"content": input_data.get("message", "")}
            response = await agent(message)
            
            # Build and return result
            return self._build_result(response)
            
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Agent execution failed: {str(e)}", agent_id=agent_id)
        finally:
            self.is_executing = False
    
    async def execute_stream(
        self,
        agent_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute agent with streaming response
        
        Args:
            agent_id: Agent ID to execute
            input_data: Input data containing message
            conversation_id: Optional conversation ID
            
        Yields:
            Streaming chunks with type, content, and done flag
        """
        self.is_executing = True
        try:
            # Load agent configuration
            role_config = await self._load_agent_config(agent_id)
            
            # Initialize context
            self.context.init(role_config, input_data, conversation_id)
            
            # Create toolkit
            toolkit = await self._create_toolkit(role_config)
            
            # Build system prompt
            identity = role_config.get("identity", {})
            sys_prompt = self.factory._build_sys_prompt(identity, {})
            
            # Get LLM config
            capabilities = role_config.get("capabilities", {})
            llm_config = capabilities.get("llm", {})
            model_name = llm_config.get("model", "gpt-4")
            
            # Create agent
            agent = await self.factory.create_agent(
                model_name=model_name,
                sys_prompt=sys_prompt,
                tools=toolkit.get_tool_schemas() if toolkit.get_tool_schemas() else None
            )
            
            # Stream response
            message = {"content": input_data.get("message", "")}
            async for chunk in agent.stream_reply(message):
                yield {
                    "type": "chunk",
                    "content": getattr(chunk, 'content', str(chunk)),
                    "done": False
                }
            
            # Send completion marker
            yield {"type": "complete", "content": "", "done": True}
            
        except Exception as e:
            yield {"type": "error", "content": str(e), "done": True}
        finally:
            self.is_executing = False
    
    async def _load_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Load agent configuration from database
        
        Args:
            agent_id: Agent ID to load
            
        Returns:
            Agent configuration dictionary
            
        Raises:
            AgentError: If agent not found
        """
        async with async_session_maker() as db:
            from models.agent import Agent
            from sqlalchemy import select
            
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise AgentError(f"Agent {agent_id} not found", agent_id=agent_id)
            
            return agent.to_dict()
    
    async def _create_toolkit(self, role_config: Dict[str, Any]) -> AgentToolkit:
        """Create toolkit with registered skills
        
        Args:
            role_config: Agent role configuration
            
        Returns:
            AgentToolkit with registered skills
        """
        toolkit = AgentToolkit()
        
        capabilities = role_config.get("capabilities", {})
        skills = capabilities.get("skills", [])
        
        # Import skill registry
        from agent.skills.base import skill_registry
        
        for skill_binding in skills:
            skill_id = skill_binding.get("skillId") or skill_binding.get("skill_id")
            skill = skill_registry.get(skill_id)
            if skill:
                await toolkit.register_skill(skill)
        
        return toolkit
    
    def _build_result(self, response: Any) -> Dict[str, Any]:
        """Build execution result from agent response
        
        Args:
            response: Agent response object
            
        Returns:
            Result dictionary with type, content, tool_calls, metadata
        """
        return {
            "type": "response",
            "content": getattr(response, 'content', str(response)),
            "tool_calls": getattr(response, 'tool_calls', []),
            "metadata": getattr(response, 'metadata', {})
        }