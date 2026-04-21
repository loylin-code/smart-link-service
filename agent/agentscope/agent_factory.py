"""AgentFactory - Creates and configures AgentScope agents."""
import os
from typing import List, Dict, Any, Optional


class AgentFactory:
    """
    Factory for creating AgentScope agents with configured models.
    """
    
    def __init__(self) -> None:
        """Initialize AgentFactory with default model configurations."""
        self._default_model = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
        self._default_temperature = 0.7
    
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
    
    def _create_model(self, model_name: str) -> Any:
        """
        Create a ChatModelBase instance based on model name.
        
        Args:
            model_name: Model name (e.g., "gpt-4o-mini", "claude-3-opus")
        
        Returns:
            ChatModelBase instance
        """
        from agentscope.model import OpenAIChatModel, AnthropicChatModel
        
        # Detect model provider from name
        if model_name.startswith("claude") or model_name.startswith("anthropic"):
            return AnthropicChatModel(
                model_name=model_name,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                stream=True
            )
        else:
            # Default to OpenAI-compatible (works with LiteLLM too)
            return OpenAIChatModel(
                model_name=model_name,
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LITELLM_API_KEY"),
                stream=True,
                client_kwargs={
                    "base_url": os.getenv("OPENAI_BASE_URL") or os.getenv("LITELLM_BASE_URL")
                } if os.getenv("OPENAI_BASE_URL") or os.getenv("LITELLM_BASE_URL") else None
            )
    
    def _create_formatter(self, model_name: str) -> Any:
        """
        Create appropriate formatter for the model.
        
        Args:
            model_name: Model name to determine formatter
        
        Returns:
            FormatterBase instance
        """
        from agentscope.formatter import OpenAIChatFormatter, AnthropicChatFormatter
        
        if model_name.startswith("claude") or model_name.startswith("anthropic"):
            return AnthropicChatFormatter()
        else:
            return OpenAIChatFormatter()
    
    async def create_agent(
        self,
        model_name: str,
        sys_prompt: str,
        tools: Optional[Any] = None
    ) -> Any:
        """
        Create an AgentScope ReActAgent instance.
        
        Args:
            model_name: Name of the model to use
            sys_prompt: System prompt for the agent
            tools: Optional Toolkit instance or list of tool schemas
        
        Returns:
            Configured ReActAgent instance
        """
        from agentscope.agent import ReActAgent
        from agentscope.tool import Toolkit
        
        model = self._create_model(model_name)
        formatter = self._create_formatter(model_name)
        
        # Handle tools: can be Toolkit object or list of schemas
        toolkit = None
        if tools is not None:
            if hasattr(tools, 'register_tool_function'):
                # It's already a Toolkit-like object
                toolkit = tools
            elif isinstance(tools, list):
                # It's a list of tool schemas - create Toolkit and register
                toolkit = Toolkit()
                for tool_schema in tools:
                    if isinstance(tool_schema, dict) and 'function' in tool_schema:
                        # Register tool function from schema
                        toolkit.register_tool_function(
                            tool_schema['function'].get('name', 'unknown'),
                            tool_schema['function'].get('description', ''),
                            tool_schema['function'].get('parameters', {})
                        )
        
        agent = ReActAgent(
            name="agent",
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit
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
            model_name: Name of the model to use
            sys_prompt: System prompt for the agent
            memory: Memory configuration with history/context
            tools: Optional list of tools/functions for the agent
        
        Returns:
            Configured ReActAgent instance
        """
        from agentscope.agent import ReActAgent
        from agentscope.memory import InMemoryMemory
        
        model = self._create_model(model_name)
        formatter = self._create_formatter(model_name)
        
        # Create memory instance
        agent_memory = InMemoryMemory()
        
        agent = ReActAgent(
            name="agent",
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=tools,
            memory=agent_memory
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
        model_name = self._default_model
        
        model = self._create_model(model_name)
        formatter = self._create_formatter(model_name)
        
        agent = ReActAgent(
            name=role_config.get("code", "sub_agent"),
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit if hasattr(toolkit, '_tools') else None
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
        model_name = self._default_model
        
        model = self._create_model(model_name)
        formatter = self._create_formatter(model_name)
        
        agent = ReActAgent(
            name="PlanAgent",
            sys_prompt=sys_prompt,
            model=model,
            formatter=formatter,
            toolkit=toolkit if hasattr(toolkit, '_tools') else None
        )
        
        return agent