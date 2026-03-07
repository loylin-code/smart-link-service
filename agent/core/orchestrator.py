"""
Updated orchestrator with parallel workflow execution
"""
from typing import Dict, Any, List, Optional, AsyncIterator
import asyncio
from datetime import datetime

from agent.core.context import AgentContext
from agent.core.executor import WorkflowExecutor
from agent.core.memory import MemoryManager
from agent.llm.client import LLMClient
from agent.skills.base import skill_registry
from agent.mcp.client import mcp_manager
from core.config import settings
from core.exceptions import AgentError
from services.conversation_service import ConversationService
from db.session import async_session_maker


class AgentOrchestrator:
    """Agent orchestrator with parallel workflow execution"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.llm_client = LLMClient(self.config.get("llm", {}))
        self.context = AgentContext()
        self.available_tools: List[Dict[str, Any]] = []
        self.is_executing = False
    
    async def execute(self, app_id: str, input_data: Dict[str, Any], conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute agent workflow"""
        self.is_executing = True
        try:
            app_config = await self._load_app_config(app_id)
            self.context.init(app_config, input_data, conversation_id)
            
            if conversation_id:
                await self._load_conversation_history(conversation_id)
            
            self.available_tools = self._get_available_tools(app_config)
            
            if "nodes" in app_config.get("schema", {}):
                executor = WorkflowExecutor(app_config["schema"], self.context)
                results = await executor.execute()
                self.context.set_result(results)
            else:
                await self._execute_chat()
            
            if conversation_id:
                await self._save_conversation(conversation_id)
            
            return self.context.get_final_result()
        except Exception as e:
            raise AgentError(f"Agent execution failed: {str(e)}", agent_id=app_id)
        finally:
            self.is_executing = False
    
    async def execute_stream(self, app_id: str, input_data: Dict[str, Any], conversation_id: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """Execute agent with streaming response"""
        self.is_executing = True
        try:
            app_config = await self._load_app_config(app_id)
            self.context.init(app_config, input_data, conversation_id)
            self.available_tools = self._get_available_tools(app_config)
            
            async for chunk in self._stream_llm_response():
                yield chunk
            
            if conversation_id:
                await self._save_conversation(conversation_id)
        except Exception as e:
            yield {"type": "error", "content": str(e)}
        finally:
            self.is_executing = False
    
    async def _load_app_config(self, app_id: str) -> Dict[str, Any]:
        async with async_session_maker() as db:
            from models import Application
            from sqlalchemy import select
            result = await db.execute(select(Application).where(Application.id == app_id))
            app = result.scalar_one_or_none()
            if not app:
                raise AgentError(f"Application {app_id} not found", agent_id=app_id)
            return {"id": app.id, "name": app.name, "schema": app.schema or {}, "skills": app.skills or []}
    
    async def _load_conversation_history(self, conversation_id: str):
        async with async_session_maker() as db:
            service = ConversationService(db)
            messages = await service.get_messages(conversation_id)
            for msg in messages:
                content = msg.content.get("text", "")
                if content:
                    self.context.add_message(msg.role, content)
    
    async def _save_conversation(self, conversation_id: str):
        async with async_session_maker() as db:
            service = ConversationService(db)
            existing = await service.get_messages(conversation_id)
            existing_count = len(existing)
            for msg in self.context.messages[existing_count:]:
                await service.add_message(conversation_id=conversation_id, role=msg["role"], content={"text": msg["content"]})
    
    def _get_available_tools(self, app_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        tools = []
        for skill_name in app_config.get("skills", []):
            skill = skill_registry.get(skill_name)
            if skill:
                tools.append(skill.to_openai_tool())
        # Add MCP tools
        tools.extend(mcp_manager.get_all_tools())
        return tools if tools else skill_registry.get_all_tools()
    
    async def _execute_chat(self):
        response = await self.llm_client.chat(messages=self.context.get_messages(), tools=self.available_tools or None)
        if response.get("content"):
            self.context.add_message("assistant", response["content"])
        if "tool_calls" in response:
            await self._handle_tool_calls(response["tool_calls"])
            await self._execute_chat()
    
    async def _handle_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        import json
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            try:
                args = json.loads(tool_call["function"]["arguments"])
            except:
                args = {}
            
            # Try skill first, then MCP
            skill = skill_registry.get(tool_name)
            if skill:
                result = await skill.execute(self.context, args)
            else:
                result = await mcp_manager.call_tool(tool_name, args)
            
            self.context.add_message("tool", json.dumps(result))
            self.context.add_tool_result(tool_call["id"], result)
    
    async def _stream_llm_response(self) -> AsyncIterator[Dict[str, Any]]:
        full_content = ""
        async for chunk in self.llm_client.chat_stream(messages=self.context.get_messages(), tools=self.available_tools or None):
            content = chunk.get("content", "")
            full_content += content
            yield {"type": "chunk", "content": content}
        self.context.add_message("assistant", full_content)
        yield {"type": "complete", "content": full_content}