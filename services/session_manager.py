"""
Redis Session Manager for distributed session storage
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import redis.asyncio as redis
from pydantic import BaseModel

from core.config import settings
from core.exceptions import RedisError


class SessionData(BaseModel):
    """Session data structure"""
    session_id: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: str
    app_id: Optional[str] = None
    conversation_id: Optional[str] = None
    state: str = "active"
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any] = {}


class SessionManager:
    """
    Redis-based session manager for distributed session storage
    
    Features:
    - Session creation and retrieval
    - Session expiration and cleanup
    - Pub/Sub for real-time updates
    - Connection tracking
    """
    
    # Redis key prefixes
    KEY_PREFIX = "session"
    TENANT_PREFIX = "tenant"
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis = await redis.Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            print("[OK] SessionManager connected to Redis")
        except Exception as e:
            raise RedisError(f"Failed to connect to Redis: {str(e)}", operation="connect")
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
    
    # ==================== Session Operations ====================
    
    async def create_session(
        self,
        client_id: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        app_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        ttl: int = None
    ) -> SessionData:
        """
        Create a new session
        
        Args:
            client_id: Unique client identifier
            user_id: User ID (if authenticated)
            tenant_id: Tenant ID
            app_id: Application ID
            conversation_id: Conversation ID
            ttl: Session TTL in seconds
            
        Returns:
            SessionData object
        """
        import secrets
        session_id = secrets.token_urlsafe(16)
        now = datetime.utcnow()
        
        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            client_id=client_id,
            app_id=app_id,
            conversation_id=conversation_id,
            state="active",
            created_at=now,
            last_activity=now
        )
        
        # Store in Redis
        key = self._session_key(tenant_id or "public", session_id)
        ttl = ttl or settings.SESSION_EXPIRE_SECONDS
        
        await self.redis.setex(
            key,
            ttl,
            session.model_dump_json()
        )
        
        # Add to tenant's session set
        if tenant_id:
            await self.redis.sadd(
                self._tenant_sessions_key(tenant_id),
                session_id
            )
        
        return session
    
    async def get_session(
        self,
        tenant_id: str,
        session_id: str
    ) -> Optional[SessionData]:
        """
        Get session by ID
        
        Args:
            tenant_id: Tenant ID
            session_id: Session ID
            
        Returns:
            SessionData or None
        """
        key = self._session_key(tenant_id, session_id)
        data = await self.redis.get(key)
        
        if not data:
            return None
        
        return SessionData.model_validate_json(data)
    
    async def update_session(
        self,
        tenant_id: str,
        session_id: str,
        updates: Dict[str, Any]
    ) -> Optional[SessionData]:
        """
        Update session data
        
        Args:
            tenant_id: Tenant ID
            session_id: Session ID
            updates: Fields to update
            
        Returns:
            Updated SessionData or None
        """
        session = await self.get_session(tenant_id, session_id)
        if not session:
            return None
        
        # Update fields
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.last_activity = datetime.utcnow()
        
        # Save back to Redis
        key = self._session_key(tenant_id, session_id)
        ttl = await self.redis.ttl(key)
        
        if ttl > 0:
            await self.redis.setex(
                key,
                ttl,
                session.model_dump_json()
            )
        
        return session
    
    async def delete_session(
        self,
        tenant_id: str,
        session_id: str
    ) -> bool:
        """
        Delete a session
        
        Args:
            tenant_id: Tenant ID
            session_id: Session ID
            
        Returns:
            True if deleted
        """
        key = self._session_key(tenant_id, session_id)
        result = await self.redis.delete(key)
        
        # Remove from tenant's session set
        await self.redis.srem(
            self._tenant_sessions_key(tenant_id),
            session_id
        )
        
        return result > 0
    
    async def get_tenant_sessions(
        self,
        tenant_id: str
    ) -> List[SessionData]:
        """
        Get all active sessions for a tenant
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            List of SessionData
        """
        session_ids = await self.redis.smembers(
            self._tenant_sessions_key(tenant_id)
        )
        
        sessions = []
        for session_id in session_ids:
            session = await self.get_session(tenant_id, session_id)
            if session:
                sessions.append(session)
        
        return sessions
    
    async def get_session_count(self, tenant_id: str) -> int:
        """Get active session count for tenant"""
        return await self.redis.scard(
            self._tenant_sessions_key(tenant_id)
        )
    
    async def refresh_session(
        self,
        tenant_id: str,
        session_id: str,
        ttl: int = None
    ) -> bool:
        """
        Refresh session TTL
        
        Args:
            tenant_id: Tenant ID
            session_id: Session ID
            ttl: New TTL in seconds
            
        Returns:
            True if refreshed
        """
        key = self._session_key(tenant_id, session_id)
        ttl = ttl or settings.SESSION_EXPIRE_SECONDS
        
        # Update last_activity
        session = await self.get_session(tenant_id, session_id)
        if session:
            session.last_activity = datetime.utcnow()
            await self.redis.setex(key, ttl, session.model_dump_json())
            return True
        return False
    
    # ==================== Pub/Sub Operations ====================
    
    async def publish(
        self,
        tenant_id: str,
        channel: str,
        message: Dict[str, Any]
    ):
        """
        Publish message to a channel
        
        Args:
            tenant_id: Tenant ID
            channel: Channel name
            message: Message data
        """
        full_channel = self._channel_key(tenant_id, channel)
        await self.redis.publish(full_channel, json.dumps(message))
    
    async def subscribe(
        self,
        tenant_id: str,
        channel: str,
        callback
    ):
        """
        Subscribe to a channel
        
        Args:
            tenant_id: Tenant ID
            channel: Channel name
            callback: Async callback function
        """
        if not self.pubsub:
            self.pubsub = self.redis.pubsub()
        
        full_channel = self._channel_key(tenant_id, channel)
        await self.pubsub.subscribe(full_channel)
        
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await callback(data)
                except Exception as e:
                    print(f"Error processing message: {e}")
    
    async def unsubscribe(
        self,
        tenant_id: str,
        channel: str
    ):
        """Unsubscribe from a channel"""
        if self.pubsub:
            full_channel = self._channel_key(tenant_id, channel)
            await self.pubsub.unsubscribe(full_channel)
    
    # ==================== Lane Queue Operations ====================
    
    async def enqueue_lane(
        self,
        tenant_id: str,
        user_id: str,
        task: Dict[str, Any],
        priority: int = 0
    ) -> str:
        """
        Add task to user's lane queue
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            task: Task data
            priority: Task priority (higher = more important)
            
        Returns:
            Task ID
        """
        import secrets
        task_id = secrets.token_urlsafe(8)
        
        queue_key = self._lane_queue_key(tenant_id, user_id)
        
        task_data = {
            "task_id": task_id,
            "data": task,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Use sorted set for priority queue
        await self.redis.zadd(
            queue_key,
            {json.dumps(task_data): -priority}  # Negative for descending order
        )
        
        return task_id
    
    async def dequeue_lane(
        self,
        tenant_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get next task from user's lane queue
        
        Args:
            tenant_id: Tenant ID
            user_id: User ID
            
        Returns:
            Task data or None
        """
        queue_key = self._lane_queue_key(tenant_id, user_id)
        
        # Get highest priority task (lowest score due to negation)
        result = await self.redis.zpopmin(queue_key)
        
        if result:
            task_json, _ = result[0]
            return json.loads(task_json)
        
        return None
    
    async def get_lane_queue_size(
        self,
        tenant_id: str,
        user_id: str
    ) -> int:
        """Get number of pending tasks in lane"""
        queue_key = self._lane_queue_key(tenant_id, user_id)
        return await self.redis.zcard(queue_key)
    
    async def get_active_lanes(
        self,
        tenant_id: str,
        user_id: str
    ) -> int:
        """Get number of active (processing) lanes for user"""
        key = self._active_lanes_key(tenant_id, user_id)
        count = await self.redis.get(key)
        return int(count) if count else 0
    
    async def increment_active_lanes(
        self,
        tenant_id: str,
        user_id: str
    ) -> int:
        """Increment active lane count and return new value"""
        key = self._active_lanes_key(tenant_id, user_id)
        return await self.redis.incr(key)
    
    async def decrement_active_lanes(
        self,
        tenant_id: str,
        user_id: str
    ):
        """Decrement active lane count"""
        key = self._active_lanes_key(tenant_id, user_id)
        await self.redis.decr(key)
    
    # ==================== Key Helpers ====================
    
    def _session_key(self, tenant_id: str, session_id: str) -> str:
        return f"{self.KEY_PREFIX}:{tenant_id}:{session_id}"
    
    def _tenant_sessions_key(self, tenant_id: str) -> str:
        return f"{self.TENANT_PREFIX}:{tenant_id}:sessions"
    
    def _channel_key(self, tenant_id: str, channel: str) -> str:
        return f"channel:{tenant_id}:{channel}"
    
    def _lane_queue_key(self, tenant_id: str, user_id: str) -> str:
        return f"lane:{tenant_id}:{user_id}:queue"
    
    def _active_lanes_key(self, tenant_id: str, user_id: str) -> str:
        return f"lane:{tenant_id}:{user_id}:active"


# Global session manager instance
session_manager = SessionManager()