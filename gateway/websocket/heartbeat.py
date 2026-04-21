"""
WebSocket心跳管理器
实现双向心跳检测和连接活跃度监控
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Callable, Any
from fastapi import WebSocket

from core.time_utils import now_utc8, UTC8
import redis.asyncio as redis


class HeartbeatManager:
    """
    WebSocket连接心跳管理器
    
    功能:
    - 心跳检测
    - 超时断开
    - 连接活跃度监控
    """
    
    DEFAULT_TIMEOUT = 60       # 心跳超时时间(秒)
    DEFAULT_INTERVAL = 30      # 心跳间隔(秒)
    MAX_MISSED_HEARTBEATS = 2  # 最大允许丢失心跳次数
    IDLE_TIMEOUT = 600         # 空闲连接自动断开时间(秒)
    
    def __init__(
        self,
        redis_client: redis.Redis,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        heartbeat_interval: int = DEFAULT_INTERVAL
    ):
        self.redis = redis_client
        self.timeout = timeout_seconds
        self.interval = heartbeat_interval
        
        # 连接存储: session_key -> connection_info
        self.connections: Dict[str, Dict[str, Any]] = {}
        
        # 回调函数
        self._on_timeout: Optional[Callable] = None
        self._monitor_task: Optional[asyncio.Task] = None
    
    def on_timeout(self, callback: Callable):
        """注册超时回调"""
        self._on_timeout = callback
    
    async def start_monitoring(self):
        """启动心跳监控循环"""
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """停止心跳监控"""
        if self._monitor_task:
            self._monitor_task.cancel()
    
    async def register_connection(
        self,
        session_key: str,
        websocket: WebSocket,
        user_id: str,
        tenant_id: str
    ):
        """注册新连接"""
        now = datetime.utcnow()
        
        self.connections[session_key] = {
            "websocket": websocket,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "connected_at": now,
            "last_ping": now,
            "last_pong": now,
            "missed_heartbeats": 0,
            "is_alive": True
        }
        
        # 持久化到Redis
        await self.redis.hset(
            f"ws:session:{session_key}",
            mapping={
                "user_id": user_id,
                "tenant_id": tenant_id,
                "connected_at": now.isoformat(),
                "last_activity": now.isoformat(),
                "status": "active"
            }
        )
    
    async def unregister_connection(self, session_key: str):
        """注销连接"""
        if session_key in self.connections:
            del self.connections[session_key]
        
        # 从Redis删除
        await self.redis.delete(f"ws:session:{session_key}")
    
    async def record_ping(self, session_key: str):
        """记录客户端心跳"""
        if session_key in self.connections:
            self.connections[session_key]["last_ping"] = datetime.now(UTC8)
            self.connections[session_key]["missed_heartbeats"] = 0
            
            # 更新Redis
            await self.redis.hset(
                f"ws:session:{session_key}",
                "last_activity",
                datetime.utcnow().isoformat()
            )
    
    async def record_pong(self, session_key: str):
        """记录服务端心跳响应"""
        if session_key in self.connections:
            self.connections[session_key]["last_pong"] = datetime.now(UTC8)
    
    async def send_heartbeat(self, session_key: str):
        """发送心跳到客户端"""
        if session_key not in self.connections:
            return
        
        conn = self.connections[session_key]
        
        try:
            await conn["websocket"].send_json({
                "type": "heartbeat",
                "timestamp": int(datetime.utcnow().timestamp() * 1000)
            })
        except Exception:
            conn["is_alive"] = False
    
    async def _monitor_loop(self):
        """定期检查连接活跃度"""
        while True:
            await asyncio.sleep(self.interval)
            
            now = datetime.now(timezone.utc)
            dead_connections = []
            
            for session_key, conn in self.connections.items():
                last_ping = conn["last_ping"]
                elapsed = (now - last_ping).total_seconds()
                
                # 检查是否超时
                if elapsed > self.timeout:
                    conn["missed_heartbeats"] += 1
                    
                    if conn["missed_heartbeats"] > self.MAX_MISSED_HEARTBEATS:
                        dead_connections.append(session_key)
                        continue
                
                # 检查空闲超时
                last_activity = conn.get("last_pong", conn["last_ping"])
                idle_time = (now - last_activity).total_seconds()
                
                if idle_time > self.IDLE_TIMEOUT:
                    dead_connections.append(session_key)
            
            # 关闭超时连接
            for session_key in dead_connections:
                await self._close_dead_connection(session_key)
    
    async def _close_dead_connection(self, session_key: str):
        """关闭超时连接"""
        if session_key not in self.connections:
            return
        
        conn = self.connections[session_key]
        
        try:
            await conn["websocket"].close(code=1001, reason="Heartbeat timeout")
        except Exception:
            pass
        
        # 触发回调
        if self._on_timeout:
            await self._on_timeout(session_key)
        
        # 清理
        await self.unregister_connection(session_key)
    
    def get_connection_count(self) -> int:
        """获取活跃连接数"""
        return len(self.connections)
    
    def get_connection_info(self, session_key: str) -> Optional[Dict[str, Any]]:
        """获取连接信息"""
        return self.connections.get(session_key)
    
    def get_all_sessions(self) -> list:
        """获取所有会话ID"""
        return list(self.connections.keys())


# 全局心跳管理器
heartbeat_manager: Optional[HeartbeatManager] = None


async def init_heartbeat_manager(redis_client: redis.Redis):
    """初始化心跳管理器"""
    global heartbeat_manager
    heartbeat_manager = HeartbeatManager(redis_client)
    await heartbeat_manager.start_monitoring()


def get_heartbeat_manager() -> Optional[HeartbeatManager]:
    return heartbeat_manager