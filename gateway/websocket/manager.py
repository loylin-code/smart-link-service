"""
WebSocket connection manager for real-time communication
"""
import json
from typing import Dict, Set, Optional, Any
from datetime import datetime
import asyncio
import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect
from core.config import settings
from core.exceptions import RedisError
from schemas.common import WSMessage


class ConnectionManager:
    """
    WebSocket connection manager
    Handles connections, message routing, and Redis pub/sub
    """
    
    def __init__(self):
        # Active WebSocket connections: {client_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}
        
        # App to clients mapping: {app_id: {client_ids}}
        self.app_clients: Dict[str, Set[str]] = {}
        
        # Redis client for pub/sub
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis = redis.Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS
            )
            
            # Test connection
            await self.redis.ping()
            print("[OK] Redis connected successfully")
            
        except Exception as e:
            raise RedisError(f"Failed to connect to Redis: {str(e)}", operation="init")
    
    async def connect(self, websocket: WebSocket, client_id: str, app_id: Optional[str] = None):
        """
        Register a new WebSocket connection
        
        Note: websocket should already be accepted by the endpoint
        
        Args:
            websocket: WebSocket connection (already accepted)
            client_id: Unique client identifier
            app_id: Application ID (optional)
        """
        # Store connection (websocket already accepted by endpoint)
        self.active_connections[client_id] = websocket
        
        # Map app to client
        if app_id:
            if app_id not in self.app_clients:
                self.app_clients[app_id] = set()
            self.app_clients[app_id].add(client_id)
        
        # Subscribe to Redis channel for this client
        await self._subscribe_client(client_id)
        
        print(f"[OK] Client {client_id} connected (app: {app_id})")
    
    def disconnect(self, client_id: str):
        """
        Remove a WebSocket connection
        
        Args:
            client_id: Client identifier to disconnect
        """
        # Remove from active connections
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        # Remove from app mappings
        for app_id, clients in self.app_clients.items():
            clients.discard(client_id)
            if not clients:
                del self.app_clients[app_id]
        
        print(f"[DISCONNECT] Client {client_id} disconnected")
    
    async def send_personal_message(self, message: Dict[str, Any], client_id: str):
        """
        Send a message to a specific client
        
        Args:
            message: Message data
            client_id: Target client ID
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast_to_app(self, message: Dict[str, Any], app_id: str):
        """
        Broadcast a message to all clients of an app
        
        Args:
            message: Message data
            app_id: Application ID
        """
        if app_id in self.app_clients:
            for client_id in self.app_clients[app_id]:
                await self.send_personal_message(message, client_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients
        
        Args:
            message: Message data
        """
        for client_id in self.active_connections:
            await self.send_personal_message(message, client_id)
    
    async def publish_to_channel(self, channel: str, message: Dict[str, Any]):
        """
        Publish a message to a Redis channel
        
        Args:
            channel: Redis channel name
            message: Message data
        """
        if self.redis:
            await self.redis.publish(channel, json.dumps(message))
    
    async def _subscribe_client(self, client_id: str):
        """
        Subscribe to Redis channel for a client
        
        Args:
            client_id: Client identifier
        """
        # This is for future use when we have multiple gateway instances
        # For now, messages are sent directly through WebSocket
        pass
    
    async def listen_redis_channels(self):
        """
        Listen to Redis channels and forward messages to WebSocket clients
        This is for horizontal scaling when multiple gateway instances exist
        """
        if not self.redis:
            return
        
        try:
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe("agent:broadcast")
            
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        channel = message["channel"]
                        
                        # Broadcast to all clients
                        if channel == "agent:broadcast":
                            await self.broadcast(data)
                        # Send to specific client
                        elif channel.startswith("agent:client:"):
                            client_id = channel.split(":")[-1]
                            await self.send_personal_message(data, client_id)
                            
                    except json.JSONDecodeError:
                        print(f"Invalid JSON in Redis message: {message['data']}")
                        
        except asyncio.CancelledError:
            print("Redis listener cancelled")
        except Exception as e:
            print(f"Redis listener error: {e}")
    
    async def close(self):
        """Close all connections and cleanup"""
        # Close Redis
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
        
        # Close all WebSocket connections
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.close()
            except Exception:
                pass
        
        self.active_connections.clear()
        self.app_clients.clear()
        
        print("[OK] Connection manager closed")


# Global connection manager instance
manager = ConnectionManager()