"""
API routes for WebSocket endpoint
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from gateway.websocket.manager import manager
from gateway.websocket.handlers import handle_chat_message, handle_ping
from gateway.middleware.auth import verify_api_key_ws
from core.config import settings

router = APIRouter()


@router.websocket("/chat/{client_id}")
async def websocket_chat(
    websocket: WebSocket,
    client_id: str,
    app_id: str = Query(..., description="Application ID"),
    api_key: str = Query(None, description="API Key for authentication")
):
    """
    WebSocket chat endpoint
    
    Connect with: ws://host/ws/chat/{client_id}?app_id={app_id}&api_key={api_key}
    
    Message format:
    {
        "type": "chat" | "ping",
        "data": {...}
    }
    """
    # Verify API key
    if not await verify_api_key_ws(websocket):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    # Connect client
    await manager.connect(websocket, client_id, app_id)
    
    try:
        # Get database session
        async with get_db() as db:
            while True:
                # Receive message
                data = await websocket.receive_json()
                
                message_type = data.get("type")
                message_data = data.get("data", {})
                
                # Handle different message types
                if message_type == "chat":
                    # Add app_id to data if not present
                    message_data.setdefault("app_id", app_id)
                    await handle_chat_message(client_id, message_data, db)
                    
                elif message_type == "ping":
                    await handle_ping(client_id)
                    
                else:
                    await manager.send_personal_message({
                        "type": "error",
                        "data": {"message": f"Unknown message type: {message_type}"}
                    }, client_id)
                    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        
    except Exception as e:
        print(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


@router.websocket("/stream/{client_id}")
async def websocket_stream(
    websocket: WebSocket,
    client_id: str,
    api_key: str = Query(None)
):
    """
    WebSocket stream endpoint for real-time agent execution
    
    Used for streaming agent responses and tool calls
    """
    # Verify API key
    if not await verify_api_key_ws(websocket):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            # Handle stream-specific messages
            await manager.send_personal_message({
                "type": "ack",
                "data": data
            }, client_id)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)