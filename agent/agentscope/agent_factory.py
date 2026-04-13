"""AgentFactory - Creates and configures AgentScope agents."""
from typing import List, Dict, Any, Optional
import asyncio


class AgentFactory:
    """
    Factory for creating AgentScope agents with configured models.
    """
    
    def __init__(self) -> None:
        """Initialize AgentFactory with default model configurations."""
        self._model_configs: Dict[str, Any] = {
            "default": {
                "model": "gpt-4",
                "temperature": 0.7,
            }
        }
    
    def _build_sys_prompt(
        self,
        identity: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> str:
        """
        Build system prompt from identity configuration.
        
        Args:
            identity: Agent identity configuration with name, persona, responsibilities
            variables: Template variables for prompt substitution
        
        Returns:
            Formatted system prompt string
        """
        name = identity.get("name", "Assistant")
        persona = identity.get("persona", "You are a helpful assistant.")
        responsibilities = identity.get("responsibilities", [])
        
        prompt_parts = [f"# {name}", "", persona]
        
        if responsibilities:
            prompt_parts.extend(["", "## Responsibilities:"])
            for resp in responsibilities:
                prompt_parts.append(f"- {resp}")
        
        return "\n".join(prompt_parts)
    
    async def create_agent(
        self,
        model_name: str,
        sys_prompt: str,
        tools: Optional[List[Any]] = None
    ) -> Any:
        """
        Create an AgentScope ReActAgent instance.
        
        Args:
            model_name: Name of the model configuration to use
            sys_prompt: System prompt for the agent
            tools: Optional list of tools/functions for the agent
        
        Returns:
            Configured ReActAgent instance
        """
        from agentscope.agent import ReActAgent
        
        model_config = self._model_configs.get(model_name, self._model_configs["default"])
        
        agent = ReActAgent(
            name="agent",
            sys_prompt=sys_prompt,
            model_config=model_config,
            tools=tools
        )
        
        return agent
    
    async def create_agent_with_memory(
        self,
        model_name: str,
        sys_prompt: str,
        memory: Dict[str, Any],
        tools: Optional[List[Any]] = None
    ) -> Any:
        """
        Create an AgentScope ReActAgent instance with memory support.
        
        Args:
            model_name: Name of the model configuration to use
            sys_prompt: System prompt for the agent
            memory: Memory configuration with history/context
            tools: Optional list of tools/functions for the agent
        
        Returns:
            Configured ReActAgent instance
        """
        from agentscope.agent import ReActAgent
        
        model_config = self._model_configs.get(model_name, self._model_configs["default"])
        
        agent = ReActAgent(
            name="agent",
            sys_prompt=sys_prompt,
            model_config=model_config,
            tools=tools
        )
        
        return agent
    
    async def create_sub_agent(
        self,
        role_config: Dict[str, Any],
        toolkit: Any
    ) -> Any:
        """
        Create a SubAgent from role configuration.
        
        Args:
            role_config: Role configuration with name, persona, responsibilities
            toolkit: Toolkit instance for tool registration
        
        Returns:
            Configured ReActAgent instance
        """
        from agentscope.agent import ReActAgent
        
        sys_prompt = self._build_sys_prompt(role_config, {})
        model_config = self._model_configs.get("default", self._model_configs["default"])
        
        agent = ReActAgent(
            name=role_config.get("code", "sub_agent"),
            sys_prompt=sys_prompt,
            model_config=model_config,
            tools=toolkit.get_tool_schemas() if hasattr(toolkit, "get_tool_schemas") else None
        )
        
        return agent
    
    async def create_plan_agent(
        self,
        sub_agents_config: List[Dict[str, Any]],
        toolkit: Any
    ) -> Any:
        """
        Create a PlanAgent that coordinates multiple sub-agents.
        
        Args:
            sub_agents_config: List of sub-agent configurations
            toolkit: Toolkit instance for tool registration
        
        Returns:
            Configured ReActAgent instance as PlanAgent
        """
        from agentscope.agent import ReActAgent
        
        sys_prompt = "# PlanAgent\n\nYou are a planning agent that coordinates multiple sub-agents to complete complex tasks.\n\n## Responsibilities:\n- Break down complex tasks into sub-tasks\n- Coordinate sub-agents execution\n- Aggregate results from sub-agents"
        model_config = self._model_configs.get("default", self._model_configs["default"])
        
        agent = ReActAgent(
            name="PlanAgent",
            sys_prompt=sys_prompt,
            model_config=model_config,
            tools=toolkit.get_tool_schemas() if hasattr(toolkit, "get_tool_schemas") else None
        )
        
        return agent
