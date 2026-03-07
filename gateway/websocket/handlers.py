"""
WebSocket message handlers
Aligned with frontend WebSocket service expectations
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from schemas import WSMessage, ChatRequest
from gateway.websocket.manager import manager
from services.conversation_service import ConversationService
from agent.core.orchestrator import AgentOrchestrator


async def handle_chat_message(
    client_id: str,
    data: Dict[str, Any],
    db: AsyncSession
):
    """
    Handle chat message from WebSocket
    
    Frontend expects:
    - Send: { type: "chat", data: { message, app_id, conversation_id, attachments } }
    - Receive: { type: "stream", data: { delta, done, conversation_id, message_id } }
    """
    try:
        # Parse request
        message = data.get("message", "")
        app_id = data.get("app_id")
        conversation_id = data.get("conversation_id")
        attachments = data.get("attachments", [])
        
        # Get or create conversation
        conversation_service = ConversationService(db)
        
        if conversation_id:
            conversation = await conversation_service.get_conversation(conversation_id)
            if not conversation:
                await manager.send_personal_message({
                    "type": "error",
                    "data": {"message": "Conversation not found"},
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }, client_id)
                return
        else:
            # Create new conversation
            conversation = await conversation_service.create_conversation(
                title=message[:50] if message else "新对话",
                app_id=app_id
            )
        
        # Add user message
        user_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="user",
            content={"text": message, "attachments": attachments}
        )
        
        # Send acknowledgment
        await manager.send_personal_message({
            "type": "status",
            "data": {
                "status": "processing",
                "conversation_id": conversation.id,
                "message_id": user_message.id
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }, client_id)
        
        # Execute agent with streaming
        orchestrator = AgentOrchestrator(config={})
        
        full_content = ""
        async for chunk in orchestrator.execute_stream(
            app_id=app_id,
            input_data={"message": message},
            conversation_id=conversation.id
        ):
            chunk_type = chunk.get("type", "chunk")
            chunk_content = chunk.get("content", "")
            
            if chunk_type == "chunk":
                full_content += chunk_content
                await manager.send_personal_message({
                    "type": "stream",
                    "data": {
                        "delta": chunk_content,
                        "done": False,
                        "conversation_id": conversation.id,
                        "message_id": None
                    },
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }, client_id)
            elif chunk_type == "complete":
                # Add assistant message to database
                assistant_message = await conversation_service.add_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content={"text": full_content}
                )
                
                # Send completion
                await manager.send_personal_message({
                    "type": "stream",
                    "data": {
                        "delta": "",
                        "done": True,
                        "conversation_id": conversation.id,
                        "message_id": assistant_message.id
                    },
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }, client_id)
            
    except Exception as e:
        # Send error
        await manager.send_personal_message({
            "type": "error",
            "data": {"message": str(e)},
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }, client_id)


async def handle_tool_call(
    client_id: str,
    data: Dict[str, Any]
):
    """
    Handle tool call request
    
    Frontend expects:
    - Send: { type: "tool_call", data: { tool_name, arguments } }
    - Receive: { type: "tool_result", data: { result, success } }
    """
    from agent.skills.base import skill_registry
    from agent.mcp.client import mcp_manager
    
    tool_name = data.get("tool_name")
    arguments = data.get("arguments", {})
    
    try:
        # Try skill first
        skill = skill_registry.get(tool_name)
        if skill:
            result = await skill.execute(None, arguments)
            await manager.send_personal_message({
                "type": "tool_result",
                "data": {
                    "tool_name": tool_name,
                    "result": result,
                    "success": True
                },
                "timestamp": int(datetime.utcnow().timestamp() * 1000)
            }, client_id)
            return
        
        # Try MCP tool
        result = await mcp_manager.call_tool(tool_name, arguments)
        await manager.send_personal_message({
            "type": "tool_result",
            "data": {
                "tool_name": tool_name,
                "result": result,
                "success": True
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }, client_id)
        
    except Exception as e:
        await manager.send_personal_message({
            "type": "tool_result",
            "data": {
                "tool_name": tool_name,
                "error": str(e),
                "success": False
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }, client_id)


async def handle_ping(client_id: str):
    """
    Handle ping message
    
    Frontend expects:
    - Send: { type: "ping", data: {} }
    - Receive: { type: "pong", data: {} }
    """
    await manager.send_personal_message({
        "type": "pong",
        "data": {},
        "timestamp": int(datetime.utcnow().timestamp() * 1000)
    }, client_id)


async def handle_status(client_id: str, data: Dict[str, Any]):
    """
    Handle status request
    """
    await manager.send_personal_message({
        "type": "status",
        "data": {
            "client_id": client_id,
            "connected": True,
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        },
        "timestamp": int(datetime.utcnow().timestamp() * 1000)
    }, client_id)