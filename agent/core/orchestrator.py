"""
Agent orchestrator - Core execution engine
"""
from typing import Dict, Any, List, Optional, AsyncIterator
import asyncio
from datetime import datetime

from agent.core.context import AgentContext
from agent.llm.client import LLMClient
from agent.skills.base import skill_registry
from core.config import settings
from core.exceptions import AgentError
from services.conversation_service import ConversationService
from db.session import async_session_maker


class AgentOrchestrator:
    """
    Agent orchestrator that coordinates skills, tools, and LLM
    Implements a hybrid approach: LangChain for base + custom orchestration
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize orchestrator
        
        Args:
            config: Configuration including LLM settings, skills, etc.
        """
        self.config = config or {}
        
        # Initialize LLM client
        llm_config = self.config.get("llm", {})
        self.llm_client = LLMClient(llm_config)
        
        # Initialize context
        self.context = AgentContext()
        
        # Available tools (from skills + MCP)
        self.available_tools: List[Dict[str, Any]] = []
        
        # Execution state
        self.is_executing = False
    
    async def execute(
        self,
        app_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute agent workflow
        
        Args:
            app_id: Application ID
            input_data: Input data from user
            conversation_id: Conversation ID (if continuing)
            
        Returns:
            Execution result
        """
        self.is_executing = True
        
        try:
            # Load app configuration
            app_config = await self._load_app_config(app_id)
            
            # Initialize context
            self.context.init(app_config, input_data, conversation_id)
            
            # Load conversation history if continuing
            if conversation_id:
                await self._load_conversation_history(conversation_id)
            
            # Get available tools for this app
            self.available_tools = self._get_available_tools(app_config)
            
            # Execute workflow
            if "nodes" in app_config.get("schema", {}):
                # Structured workflow execution
                await self._execute_workflow(app_config["schema"])
            else:
                # Simple chat-based execution
                await self._execute_chat()
            
            # Save conversation
            if conversation_id:
                await self._save_conversation(conversation_id)
            
            # Get final result
            return self.context.get_final_result()
            
        except Exception as e:
            raise AgentError(f"Agent execution failed: {str(e)}", agent_id=app_id)
        
        finally:
            self.is_executing = False
    
    async def execute_stream(
        self,
        app_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute agent with streaming response
        
        Args:
            app_id: Application ID
            input_data: Input data
            conversation_id: Conversation ID
            
        Yields:
            Stream chunks
        """
        self.is_executing = True
        
        try:
            # Load app configuration
            app_config = await self._load_app_config(app_id)
            
            # Initialize context
            self.context.init(app_config, input_data, conversation_id)
            
            # Get available tools
            self.available_tools = self._get_available_tools(app_config)
            
            # Stream LLM response
            async for chunk in self._stream_llm_response():
                yield chunk
            
            # Save conversation
            if conversation_id:
                await self._save_conversation(conversation_id)
                
        except Exception as e:
            yield {
                "type": "error",
                "content": str(e)
            }
        
        finally:
            self.is_executing = False
    
    async def _load_app_config(self, app_id: str) -> Dict[str, Any]:
        """
        Load application configuration from database
        
        Args:
            app_id: Application ID
            
        Returns:
            App configuration dict
        """
        async with async_session_maker() as db:
            from models.application import Application
            from sqlalchemy import select
            
            query = select(Application).where(Application.id == app_id)
            result = await db.execute(query)
            app = result.scalar_one_or_none()
            
            if not app:
                raise AgentError(f"Application {app_id} not found", agent_id=app_id)
            
            return {
                "id": app.id,
                "name": app.name,
                "schema": app.schema or {}
            }
    
    async def _load_conversation_history(self, conversation_id: str):
        """Load conversation history into context"""
        async with async_session_maker() as db:
            service = ConversationService(db)
            messages = await service.get_messages(conversation_id)
            
            for msg in messages:
                content = msg.content.get("text", "")
                if content:
                    self.context.add_message(msg.role, content)
    
    async def _save_conversation(self, conversation_id: str):
        """Save conversation to database"""
        async with async_session_maker() as db:
            service = ConversationService(db)
            
            # Get new messages from context
            # Get existing messages to find which are new
            existing = await service.get_messages(conversation_id)
            existing_ids = {msg.id for msg in existing}
            
            # Save new messages
            for msg in self.context.messages[len(existing):]:
                await service.add_message(
                    conversation_id=conversation_id,
                    role=msg["role"],
                    content={"text": msg["content"]}
                )
    
    def _get_available_tools(self, app_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get available tools for the app
        
        Args:
            app_config: Application configuration
            
        Returns:
            List of tool definitions
        """
        tools = []
        
        # Get skills configured for this app
        skill_names = app_config.get("schema", {}).get("skills", [])
        
        for skill_name in skill_names:
            skill = skill_registry.get(skill_name)
            if skill:
                tools.append(skill.to_openai_tool())
        
        # If no skills configured, use all available
        if not tools:
            tools = skill_registry.get_all_tools()
        
        return tools
    
    async def _execute_workflow(self, schema: Dict[str, Any]):
        """
        Execute structured workflow
        
        Args:
            schema: Workflow schema with nodes and edges
        """
        nodes = schema.get("nodes", [])
        edges = schema.get("edges", [])
        
        # Build execution graph
        # TODO: Implement topological sort and parallel execution
        
        # For now, execute nodes in order
        for node in nodes:
            result = await self._execute_node(node)
            self.context.update(node.get("id"), result)
    
    async def _execute_node(self, node: Dict[str, Any]) -> Any:
        """
        Execute a single node
        
        Args:
            node: Node configuration
            
        Returns:
            Execution result
        """
        node_type = node.get("type")
        node_config = node.get("config", {})
        
        if node_type == "llm":
            return await self._execute_llm_node(node_config)
        
        elif node_type == "skill":
            return await self._execute_skill_node(node_config)
        
        elif node_type == "tool":
            return await self._execute_tool_node(node_config)
        
        else:
            raise AgentError(f"Unknown node type: {node_type}")
    
    async def _execute_chat(self):
        """Execute simple chat-based interaction"""
        # Call LLM with tools
        response = await self.llm_client.chat(
            messages=self.context.get_messages(),
            tools=self.available_tools if self.available_tools else None
        )
        
        # Add assistant response to context
        if response.get("content"):
            self.context.add_message("assistant", response["content"])
        
        # Handle tool calls
        if "tool_calls" in response:
            await self._handle_tool_calls(response["tool_calls"])
            
            # Recursively continue until no more tool calls
            await self._execute_chat()
    
    async def _execute_llm_node(self, config: Dict[str, Any]) -> Any:
        """Execute LLM node"""
        prompt_template = config.get("prompt_template", "")
        
        # Render prompt with context
        prompt = self._render_prompt(prompt_template)
        
        # Call LLM
        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=config.get("model"),
            temperature=config.get("temperature", 0.7)
        )
        
        return response.get("content", "")
    
    async def _execute_skill_node(self, config: Dict[str, Any]) -> Any:
        """Execute skill node"""
        skill_name = config.get("skill_name")
        params = config.get("params", {})
        
        skill = skill_registry.get(skill_name)
        
        if not skill:
            raise AgentError(f"Skill not found: {skill_name}")
        
        return await skill.execute(self.context, params)
    
    async def _execute_tool_node(self, config: Dict[str, Any]) -> Any:
        """Execute tool node"""
        # TODO: Implement tool execution
        pass
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """
        Handle tool calls from LLM
        
        Args:
            tool_calls: List of tool call objects
        """
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            
            # Parse arguments
            import json
            try:
                args = json.loads(tool_args)
            except:
                args = {}
            
            # Find and execute skill
            skill = skill_registry.get(tool_name)
            
            if skill:
                result = await skill.execute(self.context, args)
                
                # Add tool result to context
                self.context.add_message("tool", json.dumps(result))
                self.context.add_tool_result(tool_call["id"], result)
            else:
                # Tool not found
                error_msg = f"Tool {tool_name} not found"
                self.context.add_message("tool", json.dumps({"error": error_msg}))
    
    async def _stream_llm_response(self) -> AsyncIterator[Dict[str, Any]]:
        """Stream LLM response"""
        full_content = ""
        
        async for chunk in self.llm_client.chat_stream(
            messages=self.context.get_messages(),
            tools=self.available_tools if self.available_tools else None
        ):
            content = chunk.get("content", "")
            full_content += content
            
            yield {
                "type": "chunk",
                "content": content
            }
        
        # Add complete response to context
        self.context.add_message("assistant", full_content)
        
        # Send completion signal
        yield {
            "type": "complete",
            "content": full_content
        }
    
    def _render_prompt(self, template: str) -> str:
        """
        Render prompt template with context
        
        Args:
            template: Prompt template string
            
        Returns:
            Rendered prompt
        """
        # Simple variable substitution
        # TODO: Implement more sophisticated templating
        result = template
        
        for key, value in self.context.state.items():
            result = result.replace(f"{{{key}}}", str(value))
        
        for key, value in self.context.variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        
        return result