"""
WebSocket请求路由器
实现SessionKey → Lane → Queue三级并发路由
"""
import asyncio
import uuid
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.websocket.lane import LaneManager, get_lane_registry
from core.exceptions import SessionNotFoundError, QuotaExceededError


@dataclass
class AgentTask:
    """Agent任务定义"""
    id: str
    session_key: str
    lane_id: Optional[str]
    tenant_id: str
    user_id: str
    app_id: Optional[str]
    message: Dict[str, Any]
    priority: int = 2
    status: str = "pending"
    created_at: float = 0.0
    assigned_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    agent_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps({
            "id": self.id,
            "session_key": self.session_key,
            "lane_id": self.lane_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "app_id": self.app_id,
            "message": self.message,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "assigned_at": self.assigned_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "agent_id": self.agent_id,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
        })
    
    @classmethod
    def from_json(cls, data: str) -> "AgentTask":
        """从JSON反序列化"""
        obj = json.loads(data)
        return cls(**obj)


class RequestRouter:
    """
    WebSocket请求路由器
    
    路由流程:
    1. 验证会话有效性
    2. 检查租户配额
    3. 获取或分配Lane
    4. 创建任务并入队
    5. 分发到Agent执行
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        db_session: AsyncSession = None
    ):
        self.redis = redis_client
        self.db = db_session
        self._task_handlers: Dict[str, callable] = {}
    
    def register_task_handler(self, task_type: str, handler: callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
    
    async def route_request(
        self,
        session_key: str,
        tenant_id: str,
        user_id: str,
        message: Dict[str, Any],
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        路由请求到Agent
        
        Args:
            session_key: 会话标识
            tenant_id: 租户ID
            user_id: 用户ID
            message: 消息内容
            priority: 优先级 (0最高)
            
        Returns:
            路由结果，包含task_id和状态
        """
        # 1. 验证会话
        session_data = await self._validate_session(session_key)
        if not session_data:
            raise SessionNotFoundError(f"Invalid session: {session_key}")
        
        # 2. 检查租户配额
        if not await self._check_quota(tenant_id):
            raise QuotaExceededError("Tenant quota exceeded")
        
        # 3. 获取Lane Manager
        lane_registry = get_lane_registry()
        if not lane_registry:
            raise RuntimeError("Lane registry not initialized")
        
        lane_manager = await lane_registry.get_manager(session_key)
        
        # 4. 创建任务
        task_id = self._generate_task_id()
        
        task = AgentTask(
            id=task_id,
            session_key=session_key,
            lane_id=None,
            tenant_id=tenant_id,
            user_id=user_id,
            app_id=message.get("app_id"),
            message=message,
            priority=priority
        )
        
        # 5. 尝试获取Lane
        lane_id = await lane_manager.acquire_lane(priority)
        
        if lane_id:
            # 有空闲Lane，立即分发
            task.lane_id = lane_id
            task.status = "dispatched"
            task.assigned_at = time.time()
            
            # 分发到Agent队列
            await self._dispatch_to_agent(task)
            
            return {
                "task_id": task_id,
                "status": "dispatched",
                "lane_id": lane_id
            }
        else:
            # 无空闲Lane，加入队列
            lane_id = await lane_manager.enqueue_task(
                task_id=task_id,
                message=message,
                priority=priority
            )
            
            if not lane_id:
                return {
                    "task_id": task_id,
                    "status": "rejected",
                    "error": "Queue full"
                }
            
            task.lane_id = lane_id
            task.status = "queued"
            
            # 持久化任务状态
            await self._persist_task(task)
            
            # 估算等待时间
            estimated_wait = await self._estimate_wait_time(session_key)
            
            return {
                "task_id": task_id,
                "status": "queued",
                "lane_id": lane_id,
                "estimated_wait": estimated_wait
            }
    
    async def on_task_completed(
        self,
        task_id: str,
        session_key: str,
        lane_id: str,
        success: bool = True,
        result: Any = None
    ):
        """
        任务完成回调
        
        Args:
            task_id: 任务ID
            session_key: 会话标识
            lane_id: Lane ID
            success: 是否成功
            result: 执行结果
        """
        lane_registry = get_lane_registry()
        if not lane_registry:
            return
        
        lane_manager = await lane_registry.get_manager(session_key)
        
        # 释放Lane，获取下一个任务
        next_task = await lane_manager.release_lane(lane_id, task_id)
        
        # 更新任务状态
        await self._update_task_status(task_id, "completed" if success else "failed")
        
        # 如果有下一个任务，继续执行
        if next_task:
            task = await self._get_task(next_task.task_id)
            if task:
                await self._dispatch_to_agent(task)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        
        if not task_data:
            return False
        
        status = task_data.get(b"status", b"").decode()
        
        if status in ["completed", "failed", "cancelled"]:
            return False
        
        # 更新状态
        await self._update_task_status(task_id, "cancelled")
        
        return True
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        
        if not task_data:
            return None
        
        return {
            "task_id": task_id,
            "status": task_data.get(b"status", b"").decode(),
            "created_at": float(task_data.get(b"created_at", 0)),
            "lane_id": task_data.get(b"lane_id", b"").decode() if task_data.get(b"lane_id") else None,
        }
    
    def _generate_task_id(self) -> str:
        """生成任务ID"""
        return f"task_{uuid.uuid4().hex[:12]}"
    
    async def _validate_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        """验证会话有效性"""
        session_data = await self.redis.hgetall(f"ws:session:{session_key}")
        
        if not session_data:
            return None
        
        return {
            "user_id": session_data.get(b"user_id", b"").decode(),
            "tenant_id": session_data.get(b"tenant_id", b"").decode(),
            "status": session_data.get(b"status", b"").decode(),
        }
    
    async def _check_quota(self, tenant_id: str) -> bool:
        """检查租户配额"""
        # 获取租户当前使用量
        current_tasks = await self.redis.get(f"tenant:{tenant_id}:active_tasks")
        max_tasks = await self.redis.get(f"tenant:{tenant_id}:max_tasks")
        
        if current_tasks and max_tasks:
            if int(current_tasks) >= int(max_tasks):
                return False
        
        return True
    
    async def _dispatch_to_agent(self, task: AgentTask):
        """分发任务到Agent队列"""
        # 增加活跃任务计数
        await self.redis.incr(f"tenant:{task.tenant_id}:active_tasks")
        
        # 推送到Agent任务队列
        queue_key = f"agent:task_queue:{task.tenant_id}"
        await self.redis.lpush(queue_key, task.to_json())
        
        # 持久化任务状态
        await self._persist_task(task)
        
        # 发布任务通知
        await self.redis.publish(
            f"agent:new_task:{task.tenant_id}",
            json.dumps({
                "task_id": task.id,
                "priority": task.priority
            })
        )
    
    async def _persist_task(self, task: AgentTask):
        """持久化任务状态"""
        await self.redis.hset(
            f"task:{task.id}",
            mapping={
                "status": task.status,
                "tenant_id": task.tenant_id,
                "created_at": task.created_at,
                "session_key": task.session_key,
                "lane_id": task.lane_id or "",
                "priority": task.priority,
            }
        )
        # 设置过期时间 (1小时)
        await self.redis.expire(f"task:{task.id}", 3600)
    
    async def _update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        await self.redis.hset(f"task:{task_id}", "status", status)
        await self.redis.hset(f"task:{task_id}", "completed_at", time.time())
        
        # 减少活跃任务计数
        task_data = await self.redis.hget(f"task:{task_id}", "tenant_id")
        if task_data:
            tenant_id = task_data.decode()
            await self.redis.decr(f"tenant:{tenant_id}:active_tasks")
    
    async def _get_task(self, task_id: str) -> Optional[AgentTask]:
        """获取任务详情"""
        task_data = await self.redis.hgetall(f"task:{task_id}")
        
        if not task_data:
            return None
        
        # 从队列中获取完整任务数据
        # 这里简化处理，实际需要更完整的任务数据存储
        return AgentTask(
            id=task_id,
            session_key=task_data.get(b"session_key", b"").decode(),
            lane_id=task_data.get(b"lane_id", b"").decode() if task_data.get(b"lane_id") else None,
            tenant_id=task_data.get(b"tenant_id", b"").decode(),
            user_id="",
            message={},
            priority=int(task_data.get(b"priority", 2))
        )
    
    async def _estimate_wait_time(self, session_key: str) -> int:
        """估算等待时间"""
        lane_registry = get_lane_registry()
        if not lane_registry:
            return 0
        
        lane_manager = await lane_registry.get_manager(session_key)
        
        # 简单估算: 每个任务平均30秒
        queue_length = lane_manager.get_total_queue_length()
        return queue_length * 30


# 全局路由器实例
router: Optional[RequestRouter] = None


async def init_router(redis_client: redis.Redis, db_session: AsyncSession = None):
    """初始化全局路由器"""
    global router
    router = RequestRouter(redis_client, db_session)


def get_router() -> Optional[RequestRouter]:
    """获取全局路由器"""
    return router