"""
Lane并发模型实现
参考OpenClaw的Lane-based Command Queue模式
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

import redis.asyncio as redis


class LaneStatus(str, Enum):
    """Lane状态"""
    IDLE = "idle"           # 空闲，可接受任务
    BUSY = "busy"           # 忙碌，正在处理任务
    QUEUED = "queued"       # 有排队任务


@dataclass
class LaneTask:
    """Lane任务"""
    task_id: str
    priority: int = 0
    created_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    message: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class Lane:
    """Lane定义"""
    id: str                         # Lane ID (lane_1, lane_2, lane_3)
    session_key: str                # 所属Session
    status: LaneStatus = LaneStatus.IDLE
    current_task: Optional[str] = None  # 当前任务ID
    queue: List[LaneTask] = field(default_factory=list)  # 排队任务
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def queue_length(self) -> int:
        """获取队列长度"""
        return len(self.queue)
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.status == LaneStatus.IDLE


class LaneManager:
    """
    Lane并发管理器
    
    实现OpenClaw的Lane并发模型:
    - 每个Session默认3个Lane
    - 同一Lane内任务严格序列执行
    - 不同Lane可以并行执行
    - Lane满时任务进入等待队列
    
    使用场景:
    - 避免同一用户的多请求Race Condition
    - 提供可控的并发能力
    - 优先级队列支持
    """
    
    MAX_LANES = 3  # 每用户最大并发Lane数
    MAX_QUEUE_SIZE = 100  # 每Lane最大排队任务数
    
    def __init__(self, session_key: str, redis_client: redis.Redis):
        self.session_key = session_key
        self.redis = redis_client
        self.lanes: Dict[str, Lane] = {}
        self._lock = asyncio.Lock()
        
        # 初始化Lanes
        for i in range(1, self.MAX_LANES + 1):
            lane_id = f"lane_{i}"
            self.lanes[lane_id] = Lane(id=lane_id, session_key=session_key)
    
    async def acquire_lane(self, priority: int = 0) -> Optional[str]:
        """
        获取可用Lane
        
        策略:
        1. 优先找空闲Lane
        2. 无空闲Lane时返回None，需要入队
        
        Args:
            priority: 任务优先级 (0最高，数字越大优先级越低)
            
        Returns:
            lane_id 或 None (无可用Lane)
        """
        async with self._lock:
            # 优先找空闲Lane
            for lane_id, lane in self.lanes.items():
                if lane.status == LaneStatus.IDLE:
                    lane.status = LaneStatus.BUSY
                    lane.last_activity = datetime.utcnow()
                    await self._persist_lane_status(lane)
                    return lane_id
            
            # 无空闲Lane
            return None
    
    async def release_lane(self, lane_id: str, task_id: str) -> Optional[LaneTask]:
        """
        释放Lane
        
        如果队列中有等待任务，返回下一个任务
        否则将Lane标记为IDLE
        
        Args:
            lane_id: Lane ID
            task_id: 完成的任务ID
            
        Returns:
            下一个待执行的任务，或None
        """
        async with self._lock:
            if lane_id not in self.lanes:
                return None
            
            lane = self.lanes[lane_id]
            
            # 检查是否有排队任务
            if lane.queue:
                # 按优先级排序取出最高优先级任务
                lane.queue.sort(key=lambda t: t.priority)
                next_task = lane.queue.pop(0)
                lane.current_task = next_task.task_id
                lane.last_activity = datetime.utcnow()
                await self._persist_lane_status(lane)
                return next_task
            else:
                # 无排队任务，Lane变为IDLE
                lane.status = LaneStatus.IDLE
                lane.current_task = None
                lane.last_activity = datetime.utcnow()
                await self._persist_lane_status(lane)
                return None
    
    async def enqueue_task(
        self,
        task_id: str,
        message: Dict[str, Any] = None,
        priority: int = 0
    ) -> Optional[str]:
        """
        将任务加入等待队列
        
        选择队列最短的Lane加入
        
        Args:
            task_id: 任务ID
            message: 任务消息
            priority: 优先级 (0最高)
            
        Returns:
            排队的Lane ID，或None (队列已满)
        """
        async with self._lock:
            # 找到队列最短的Lane
            best_lane = min(
                self.lanes.values(),
                key=lambda l: l.queue_length()
            )
            
            # 检查队列是否已满
            if best_lane.queue_length() >= self.MAX_QUEUE_SIZE:
                return None
            
            # 创建任务
            task = LaneTask(
                task_id=task_id,
                priority=priority,
                message=message or {}
            )
            
            best_lane.queue.append(task)
            
            # 如果Lane是IDLE状态，标记为QUEUED
            if best_lane.status == LaneStatus.IDLE:
                best_lane.status = LaneStatus.QUEUED
            
            best_lane.last_activity = datetime.utcnow()
            await self._persist_lane_status(best_lane)
            
            return best_lane.id
    
    def get_lane_status(self) -> Dict[str, Any]:
        """获取所有Lane状态"""
        return {
            lane_id: {
                "status": lane.status.value,
                "current_task": lane.current_task,
                "queue_length": lane.queue_length()
            }
            for lane_id, lane in self.lanes.items()
        }
    
    def get_available_lane_count(self) -> int:
        """获取可用Lane数量"""
        return sum(1 for lane in self.lanes.values() if lane.status == LaneStatus.IDLE)
    
    def get_busy_lane_count(self) -> int:
        """获取忙碌Lane数量"""
        return sum(1 for lane in self.lanes.values() if lane.status == LaneStatus.BUSY)
    
    def get_total_queue_length(self) -> int:
        """获取所有Lane的总队列长度"""
        return sum(lane.queue_length() for lane in self.lanes.values())
    
    async def _persist_lane_status(self, lane: Lane):
        """持久化Lane状态到Redis"""
        key = f"session:{self.session_key}:lanes"
        await self.redis.hset(
            key,
            lane.id,
            json.dumps({
                "status": lane.status.value,
                "current_task": lane.current_task,
                "queue": [
                    {"task_id": t.task_id, "priority": t.priority}
                    for t in lane.queue
                ],
                "last_activity": lane.last_activity.isoformat()
            })
        )
        # 设置过期时间 (24小时)
        await self.redis.expire(key, 86400)
    
    async def load_lane_status(self):
        """从Redis加载Lane状态"""
        key = f"session:{self.session_key}:lanes"
        data = await self.redis.hgetall(key)
        
        if not data:
            return
        
        for lane_id, lane_data in data.items():
            if isinstance(lane_id, bytes):
                lane_id = lane_id.decode()
            
            try:
                lane_info = json.loads(lane_data)
                if lane_id in self.lanes:
                    lane = self.lanes[lane_id]
                    lane.status = LaneStatus(lane_info.get("status", "idle"))
                    lane.current_task = lane_info.get("current_task")
                    
                    # 恢复队列
                    queue_data = lane_info.get("queue", [])
                    lane.queue = [
                        LaneTask(
                            task_id=t.get("task_id"),
                            priority=t.get("priority", 0)
                        )
                        for t in queue_data
                    ]
            except Exception as e:
                print(f"Error loading lane status: {e}")


class LaneManagerRegistry:
    """
    Lane Manager注册表
    管理所有Session的Lane Manager
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._managers: Dict[str, LaneManager] = {}
        self._lock = asyncio.Lock()
    
    async def get_manager(self, session_key: str) -> LaneManager:
        """
        获取或创建Lane Manager
        
        Args:
            session_key: Session标识
            
        Returns:
            LaneManager实例
        """
        async with self._lock:
            if session_key not in self._managers:
                manager = LaneManager(session_key, self.redis)
                await manager.load_lane_status()
                self._managers[session_key] = manager
            
            return self._managers[session_key]
    
    async def remove_manager(self, session_key: str):
        """移除Lane Manager"""
        async with self._lock:
            if session_key in self._managers:
                del self._managers[session_key]
    
    def get_active_session_count(self) -> int:
        """获取活跃Session数量"""
        return len(self._managers)
    
    def get_global_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        total_available = 0
        total_busy = 0
        total_queued = 0
        
        for manager in self._managers.values():
            total_available += manager.get_available_lane_count()
            total_busy += manager.get_busy_lane_count()
            total_queued += manager.get_total_queue_length()
        
        return {
            "active_sessions": len(self._managers),
            "total_available_lanes": total_available,
            "total_busy_lanes": total_busy,
            "total_queued_tasks": total_queued,
            "max_lanes_per_session": LaneManager.MAX_LANES
        }


# 全局Lane Manager注册表
lane_registry: Optional[LaneManagerRegistry] = None


async def init_lane_registry(redis_client: redis.Redis):
    """初始化全局Lane Manager注册表"""
    global lane_registry
    lane_registry = LaneManagerRegistry(redis_client)


def get_lane_registry() -> Optional[LaneManagerRegistry]:
    """获取全局Lane Manager注册表"""
    return lane_registry