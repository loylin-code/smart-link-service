"""
WebSocket message handlers
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.common import WSMessage, ChatRequest, ChatResponse
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
    
    Args:
        client_id: Client identifier
        data: Message data containing ChatRequest fields
        db: Database session
    """
    try:
        # Parse request
        request = ChatRequest(**data)
        
        # Get or create conversation
        conversation_service = ConversationService(db)
        
        if request.conversation_id:
            conversation = await conversation_service.get_conversation(request.conversation_id)
            if not conversation:
                await manager.send_personal_message({
                    "type": "error",
                    "data": {"message": "Conversation not found"},
                    "timestamp": datetime.utcnow().isoformat()
                }, client_id)
                return
        else:
            # Create new conversation
            conversation = await conversation_service.create_conversation(
                title=request.message[:50],  # Use first 50 chars as title
                app_id=request.app_id
            )
        
        # Add user message
        user_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="user",
            content={"text": request.message}
        )
        
        # Send acknowledgment
        await manager.send_personal_message({
            "type": "message_received",
            "data": {
                "conversation_id": conversation.id,
                "message_id": user_message.id
            },
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)
        
        # Execute agent
        orchestrator = AgentOrchestrator(config={})
        
        if request.stream:
            # Stream response
            async for chunk in orchestrator.execute_stream(
                app_id=request.app_id,
                input_data={"message": request.message},
                conversation_id=conversation.id
            ):
                await manager.send_personal_message({
                    "type": "chunk",
                    "data": chunk,
                    "timestamp": datetime.utcnow().isoformat()
                }, client_id)
        else:
            # Non-streaming response
            result = await orchestrator.execute(
                app_id=request.app_id,
                input_data={"message": request.message},
                conversation_id=conversation.id
            )
            
            # Add assistant message
            assistant_message = await conversation_service.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content={"text": result.get("content", "")}
            )
            
            # Send response
            await manager.send_personal_message({
                "type": "response",
                "data": {
                    "conversation_id": conversation.id,
                    "message": assistant_message.dict(),
                    "status": "completed"
                },
                "timestamp": datetime.utcnow().isoformat()
            }, client_id)
            
    except Exception as e:
        # Send error
        await manager.send_personal_message({
            "type": "error",
            "data": {"message": str(e)},
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)


async def handle_tool_call(
    client_id: str,
    data: Dict[str, Any]
):
    """
    Handle tool call request
    
    Args:
        client_id: Client identifier
        data: Tool call data
    """
    # Tool calls are handled by the agent orchestrator
    # This is for manual tool invocations from the client
    pass


async def handle_ping(client_id: str):
    """
    Handle ping message
    
    Args:
        client_id: Client identifier
    """
    await manager.send_personal_message({
        "type": "pong",
        "data": {},
        "timestamp": datetime.utcnow().isoformat()
    }, client_id)