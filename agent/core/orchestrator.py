"""
AgentScope-based Orchestrator
Replaces original orchestrator with AgentScope integration

Enhanced with Agent Intelligence Core:
- PlanAgent routing layer
- SubAgent Pool for role-based execution
- MessageHub for agent communication
"""
from typing import Dict, Any, Optional, AsyncIterator, List
from datetime import datetime

from agent.agentscope.hub import AgentHub
from agent.agentscope.agent_factory import AgentFactory
from agent.agentscope.toolkit import AgentToolkit
from agent.core.context import AgentContext
from agent.cache import agent_config_cache
from core.exceptions import AgentError
from db.session import async_session_maker


class AgentOrchestrator:
    """AgentScope-based Agent Orchestrator
    
    Manages agent execution using AgentScope framework components:
    - AgentHub: Central message coordination for multi-agent conversations
    - AgentFactory: Creates and configures AgentScope agents
    - AgentToolkit: Registers and manages Skills and MCP tools
    
    Enhanced with Agent Intelligence Core:
    - PlanAgent: Pre-routing layer for intent recognition and task routing
    - SubAgentPool: Role-based execution agents (research/code/data/doc)
    - MessageHub: In-memory queue for agent communication
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
        
        # Agent Intelligence Core components (optional)
        self.plan_agent: Optional[Any] = None
        self.subagent_pool: Optional[Any] = None
        self.message_hub: Optional[Any] = None
        self._routing_enabled = False
    
    async def initialize_routing(
        self,
        llm_client: Any,
        memory_manager: Any
    ) -> None:
        """Initialize Agent Intelligence routing components
        
        Args:
            llm_client: LLM client for PlanAgent
            memory_manager: Memory manager for context
        """
        from agent.core.plan_agent import PlanAgent
        from agent.core.message_hub import MessageHub
        from agent.subagents.pool import SubAgentPool
        
        # Create toolkit for SubAgents
        toolkit = AgentToolkit()
        
        # Initialize components
        self.plan_agent = PlanAgent(llm_client, memory_manager)
        self.message_hub = MessageHub()
        self.subagent_pool = SubAgentPool(llm_client, toolkit, memory_manager)
        
        self._routing_enabled = True
    
    async def execute_with_routing(
        self,
        agent_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute agent with intelligent routing
        
        Flow:
        1. PlanAgent processes input → ExecutionPlan
        2. MessageHub dispatches plan → SubAgentPool
        3. SubAgents execute tasks → Results
        4. Aggregate results → Final response
        
        Args:
            agent_id: Agent ID (for context/config loading)
            input_data: Input data with message
            conversation_id: Conversation ID
            
        Returns:
            Execution result with routing metadata
            
        Raises:
            AgentError: If routing not enabled or execution fails
        """
        if not self._routing_enabled:
            raise AgentError("Routing not initialized. Call initialize_routing() first.")
        
        self.is_executing = True
        try:
            # Load agent config for context
            role_config = await self._load_agent_config(agent_id)
            
            # Build context
            context = {
                "agent_id": agent_id,
                "role_config": role_config,
                "input_data": input_data
            }
            
            # 1. PlanAgent processes input
            plan = await self.plan_agent.process(
                user_input=input_data.get("message", ""),
                conversation_id=conversation_id or "",
                context=context
            )
            
            # 2. MessageHub executes plan
            results = await self.message_hub.dispatch_plan(plan, self.subagent_pool)
            
            # 3. Build routing result
            return self._build_routing_result(plan, results)
            
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Routing execution failed: {str(e)}", agent_id=agent_id)
        finally:
            self.is_executing = False
    
    def _build_routing_result(
        self,
        plan: Any,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build result from routing execution
        
        Args:
            plan: ExecutionPlan from PlanAgent
            results: Dict of task_id -> SubAgentResult
            
        Returns:
            Result dictionary with routing metadata
        """
        # Aggregate content from all successful results
        content_parts = []
        for task_id, result in results.items():
            if result.success:
                content_parts.append(result.content)
        
        return {
            "type": "routing_response",
            "content": "\n".join(content_parts),
            "routing": {
                "plan": {
                    "tasks": [t.model_dump() for t in plan.tasks],
                    "assignments": plan.assignments
                },
                "results": {
                    task_id: {
                        "success": result.success,
                        "content": result.content,
                        "execution_time": result.execution_time
                    }
                    for task_id, result in results.items()
                }
            },
            "metadata": {
                "total_tasks": len(plan.tasks),
                "successful_tasks": sum(1 for r in results.values() if r.success)
            }
        }
    
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
    
    async def execute_stream_openai(
        self,
        agent_id: str,
        execution_id: str,
        input_data: Dict[str, Any],
        include_usage: bool = False
    ) -> AsyncIterator[Any]:
        """Execute agent with OpenAI-compatible streaming response
        
        Args:
            agent_id: Agent ID to execute
            execution_id: Unique execution ID for this request
            input_data: Input data containing message and parameters
            include_usage: Whether to include usage statistics in final chunk
            
        Yields:
            ChatCompletionChunk objects for SSE streaming
        """
        import time
        import uuid
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
            UsageInfo
        )
        
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        model = f"agent:{agent_id}"
        created = int(time.time())
        token_count = 0
        
        try:
            # Stream from internal execute_stream
            async for chunk in self.execute_stream(agent_id, input_data):
                chunk_type = chunk.get("type", "chunk")
                content = chunk.get("content", "")
                
                if chunk_type == "chunk" and content:
                    token_count += len(content.split())
                    
                    # Create OpenAI-compatible chunk
                    yield ChatCompletionChunk(
                        id=chunk_id,
                        created=created,
                        model=model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(
                                    role="assistant",
                                    content=content
                                ),
                                finish_reason=None
                            )
                        ]
                    )
                
                elif chunk_type == "complete":
                    # Final chunk with finish reason
                    usage = None
                    if include_usage:
                        usage = UsageInfo(
                            prompt_tokens=len(str(input_data.get("message", "")).split()),
                            completion_tokens=token_count,
                            total_tokens=len(str(input_data.get("message", "")).split()) + token_count
                        )
                    
                    yield ChatCompletionChunk(
                        id=chunk_id,
                        created=created,
                        model=model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(),
                                finish_reason="stop"
                            )
                        ],
                        usage=usage
                    )
                    
                elif chunk_type == "error":
                    # Error will be handled by caller
                    raise AgentError(content)
                    
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Execution failed: {str(e)}")
    
    async def execute_pipeline(
        self,
        agents: List[str],
        input_data: Dict[str, Any],
        pipeline_type: "PipelineType",
        memory: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute multi-agent pipeline workflow
        
        Args:
            agents: List of agent IDs to execute in pipeline
            input_data: Input data containing message and optional parameters
            pipeline_type: Type of pipeline (SINGLE, SEQUENTIAL, PARALLEL)
            memory: Optional shared memory dict between agents
            conversation_id: Optional conversation ID for context
            
        Returns:
            Execution result dictionary with type, pipeline_type, results, and memory
            
        Raises:
            AgentError: If execution fails
        """
        self.is_executing = True
        try:
            # Import PipelineManager
            from agent.agentscope.pipeline import PipelineManager, PipelineType
            from agentscope.pipeline import FanoutPipeline
            from agentscope.message import Msg
            
            # Create pipeline manager
            pipeline_manager = PipelineManager()
            
            # Load all agent configs and create agents
            created_agents = []
            for agent_id in agents:
                role_config = await self._load_agent_config(agent_id)
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
                created_agents.append(agent)
            
            # Build input message
            input_msg = Msg(
                name="user",
                content=input_data.get("message", ""),
                role="user"
            )
            
            # Execute pipeline and collect results based on type
            results_list = []
            
            if pipeline_type == PipelineType.SINGLE:
                result = await created_agents[0](input_msg)
                results_list = [{"content": getattr(result, 'content', str(result))}]
            
            elif pipeline_type == PipelineType.SEQUENTIAL:
                # Execute sequentially and collect each agent's result
                current_msg = input_msg
                for agent in created_agents:
                    result = await agent(current_msg)
                    results_list.append({"content": getattr(result, 'content', str(result))})
                    current_msg = result  # Pass result to next agent
            
            elif pipeline_type == PipelineType.PARALLEL:
                # Execute in parallel using FanoutPipeline
                pipeline = FanoutPipeline(agents=created_agents, enable_gather=True)
                result = await pipeline(input_msg)
                if isinstance(result, list):
                    results_list = [
                        {"content": getattr(msg, 'content', str(msg))}
                        for msg in result
                    ]
                else:
                    results_list = [{"content": getattr(result, 'content', str(result))}]
            
            response = {
                "type": "pipeline_response",
                "pipeline_type": pipeline_type.value,
                "results": results_list,
                "memory": memory
            }
            
            return response
            
        except Exception as e:
            raise AgentError(f"Pipeline execution failed: {str(e)}")
        finally:
            self.is_executing = False
    
    async def execute_pipeline_stream(
        self,
        agents: List[str],
        input_data: Dict[str, Any],
        pipeline_type: "PipelineType",
        memory: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute multi-agent pipeline with streaming response
        
        Args:
            agents: List of agent IDs to execute in pipeline
            input_data: Input data containing message
            pipeline_type: Type of pipeline (SINGLE, SEQUENTIAL, PARALLEL)
            memory: Optional shared memory dict between agents
            
        Yields:
            Streaming chunks with type, content, and done flag
        """
        self.is_executing = True
        try:
            # Import PipelineManager
            from agent.agentscope.pipeline import PipelineManager, PipelineType
            from agentscope.message import Msg
            
            # Create pipeline manager
            pipeline_manager = PipelineManager()
            
            # Load all agent configs and create agents
            created_agents = []
            for agent_id in agents:
                role_config = await self._load_agent_config(agent_id)
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
                created_agents.append(agent)
            
            # Build input message
            input_msg = Msg(
                name="user",
                content=input_data.get("message", ""),
                role="user"
            )
            
            # Stream pipeline execution
            async for chunk in pipeline_manager.execute_stream(
                created_agents,
                input_msg,
                pipeline_type
            ):
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
        """Load agent configuration from cache or database
        
        Args:
            agent_id: Agent ID to load
            
        Returns:
            Agent configuration dictionary
            
        Raises:
            AgentError: If agent not found
        """
        # Initialize cache if needed
        if agent_config_cache.enabled and not agent_config_cache._initialized:
            await agent_config_cache.initialize()
        
        # Check cache first
        cached = await agent_config_cache.get_config(agent_id)
        if cached:
            return cached  # Cache hit
        
        # Cache miss - load from database
        async with async_session_maker() as db:
            from models.agent import Agent
            from sqlalchemy import select
            
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise AgentError(f"Agent {agent_id} not found", agent_id=agent_id)
            
            config = agent.to_dict()
            
            # Store in cache
            await agent_config_cache.set_config(agent_id, config)
            
            return config
    
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