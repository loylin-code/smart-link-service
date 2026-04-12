"""
Agent分发系统
任务队列和Agent池管理
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict, field

import redis.asyncio as redis


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0     # 关键任务，立即执行
    HIGH = 1         # 高优先级
    NORMAL = 2       # 普通优先级
    LOW = 3          # 低优先级
    BACKGROUND = 4   # 后台任务


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


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
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> "AgentTask":
        return cls(**json.loads(data))


class RedisPriorityQueue:
    """
    Redis优先级队列实现
    
    使用Sorted Set实现优先级队列:
    - score = priority * 1000000000 + timestamp
    - 确保同优先级下FIFO
    - 支持阻塞获取
    """
    
    def __init__(self, redis_client: redis.Redis, queue_name: str):
        self.redis = redis_client
        self.queue_key = f"queue:{queue_name}"
        self.processing_key = f"queue:{queue_name}:processing"
        self.dead_letter_key = f"queue:{queue_name}:dead_letter"
    
    async def enqueue(self, task: AgentTask) -> bool:
        """将任务加入队列"""
        # 计算优先级分数 (越小优先级越高)
        score = task.priority * 1_000_000_000 + task.created_at
        
        task.status = TaskStatus.QUEUED.value
        
        # 添加到有序集合
        await self.redis.zadd(
            self.queue_key,
            {task.to_json(): score}
        )
        
        # 更新任务状态Hash
        await self.redis.hset(
            f"task:{task.id}",
            mapping={
                "status": task.status,
                "tenant_id": task.tenant_id,
                "created_at": task.created_at,
                "queue": self.queue_key
            }
        )
        
        return True
    
    async def dequeue(self, timeout: int = 5) -> Optional[AgentTask]:
        """从队列取出优先级最高的任务"""
        # 使用zrange获取优先级最高的任务
        results = await self.redis.zrange(
            self.queue_key,
            0, 0,
            withscores=False
        )
        
        if not results:
            return None
        
        task_data = results[0]
        if isinstance(task_data, bytes):
            task_data = task_data.decode()
        
        # 从队列移除
        removed = await self.redis.zrem(self.queue_key, task_data)
        if removed == 0:
            return None
        
        task = AgentTask.from_json(task_data)
        task.status = TaskStatus.ASSIGNED.value
        task.assigned_at = time.time()
        
        # 加入处理中集合
        await self.redis.zadd(
            self.processing_key,
            {task.id: task.assigned_at + task.timeout_seconds}
        )
        
        return task
    
    async def complete(self, task_id: str, success: bool = True):
        """标记任务完成"""
        await self.redis.zrem(self.processing_key, task_id)
        
        status = TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value
        await self.redis.hset(f"task:{task_id}", "status", status)
        await self.redis.hset(f"task:{task_id}", "completed_at", str(time.time()))
    
    async def requeue(self, task: AgentTask) -> bool:
        """重新入队(用于重试)"""
        if task.retry_count >= task.max_retries:
            await self.redis.lpush(self.dead_letter_key, task.to_json())
            return False
        
        task.retry_count += 1
        task.status = TaskStatus.PENDING.value
        task.assigned_at = None
        task.agent_id = None
        
        # 延迟重试
        delay = min(2 ** task.retry_count, 60)
        task.created_at = time.time() + delay
        
        return await self.enqueue(task)
    
    async def get_queue_length(self) -> int:
        """获取队列长度"""
        return await self.redis.zcard(self.queue_key)
    
    async def get_processing_count(self) -> int:
        """获取处理中任务数"""
        return await self.redis.zcard(self.processing_key)
    
    async def recover_timeout_tasks(self) -> List[AgentTask]:
        """恢复超时任务"""
        now = time.time()
        
        timeout_tasks = await self.redis.zrangebyscore(
            self.processing_key, 0, now
        )
        
        recovered = []
        for task_id in timeout_tasks:
            if isinstance(task_id, bytes):
                task_id = task_id.decode()
            await self.redis.zrem(self.processing_key, task_id)
            
            task_data = await self.redis.hgetall(f"task:{task_id}")
            if task_data:
                recovered.append(AgentTask(
                    id=task_id,
                    session_key=task_data.get(b'session_key', b'').decode(),
                    lane_id=task_data.get(b'lane_id', b'').decode() if task_data.get(b'lane_id') else None,
                    tenant_id=task_data.get(b'tenant_id', b'').decode(),
                    user_id="",
                    message={}
                ))
        
        return recovered


class MultiTenantQueueManager:
    """多租户队列管理器"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._queues: Dict[str, RedisPriorityQueue] = {}
    
    def get_queue(self, tenant_id: str) -> RedisPriorityQueue:
        """获取租户专属队列"""
        if tenant_id not in self._queues:
            self._queues[tenant_id] = RedisPriorityQueue(
                self.redis, f"tenant:{tenant_id}"
            )
        return self._queues[tenant_id]
    
    async def get_global_stats(self) -> dict:
        """获取全局队列统计"""
        stats = {
            "total_pending": 0,
            "total_processing": 0,
            "tenant_stats": {}
        }
        
        cursor = 0
        pattern = "queue:tenant:*"
        
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern)
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode()
                tenant_id = key.split(":")[2]
                queue = self.get_queue(tenant_id)
                
                pending = await queue.get_queue_length()
                processing = await queue.get_processing_count()
                
                stats["tenant_stats"][tenant_id] = {
                    "pending": pending,
                    "processing": processing
                }
                stats["total_pending"] += pending
                stats["total_processing"] += processing
            
            if cursor == 0:
                break
        
        return stats


class AgentState(str, Enum):
    """Agent实例状态"""
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    UNHEALTHY = "unhealthy"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


@dataclass
class AgentInstance:
    """Agent实例信息"""
    id: str
    host: str
    port: int
    state: AgentState = AgentState.IDLE
    tenant_id: Optional[str] = None
    current_task: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    load_factor: float = 0.0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    task_count: int = 0
    error_count: int = 0


class AgentPoolManager:
    """
    Agent池管理器
    
    管理:
    - 实例注册与发现
    - 健康检查
    - 负载均衡
    - 自动扩缩容
    """
    
    # 允许的状态转换
    ALLOWED_TRANSITIONS = {
        AgentState.INITIALIZING: [AgentState.IDLE, AgentState.UNHEALTHY],
        AgentState.IDLE: [AgentState.BUSY, AgentState.PAUSED, AgentState.SHUTTING_DOWN, AgentState.UNHEALTHY],
        AgentState.BUSY: [AgentState.IDLE, AgentState.UNHEALTHY, AgentState.SHUTTING_DOWN],
        AgentState.PAUSED: [AgentState.IDLE, AgentState.SHUTTING_DOWN],
        AgentState.UNHEALTHY: [AgentState.IDLE, AgentState.SHUTTING_DOWN],
        AgentState.SHUTTING_DOWN: [AgentState.TERMINATED],
        AgentState.TERMINATED: []
    }
    
    def __init__(
        self,
        redis_client: redis.Redis,
        max_agents: int = 100,
        min_agents: int = 2,
        health_check_interval: int = 30
    ):
        self.redis = redis_client
        self.max_agents = max_agents
        self.min_agents = min_agents
        self.health_check_interval = health_check_interval
        
        self.agents: Dict[str, AgentInstance] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start(self):
        """启动管理器"""
        self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop(self):
        """停止管理器"""
        if self._health_check_task:
            self._health_check_task.cancel()
        await self._graceful_shutdown()
    
    async def register_agent(
        self,
        agent_id: str,
        host: str,
        port: int,
        tenant_id: Optional[str] = None,
        capabilities: Optional[List[str]] = None
    ) -> bool:
        """注册新Agent实例"""
        async with self._lock:
            if len(self.agents) >= self.max_agents:
                return False
            
            agent = AgentInstance(
                id=agent_id,
                host=host,
                port=port,
                state=AgentState.INITIALIZING,
                tenant_id=tenant_id,
                capabilities=capabilities or []
            )
            
            self.agents[agent_id] = agent
            
            # 持久化到Redis
            await self._persist_agent(agent)
            
            # 转换为IDLE状态
            agent.state = AgentState.IDLE
            await self._persist_agent(agent)
            
            return True
    
    async def unregister_agent(self, agent_id: str, force: bool = False) -> bool:
        """注销Agent实例"""
        async with self._lock:
            if agent_id not in self.agents:
                return False
            
            agent = self.agents[agent_id]
            
            if not force and agent.state == AgentState.BUSY:
                agent.state = AgentState.SHUTTING_DOWN
                await self._persist_agent(agent)
                return False
            
            agent.state = AgentState.TERMINATED
            del self.agents[agent_id]
            await self.redis.delete(f"agent:{agent_id}")
            
            return True
    
    async def assign_task(self, task: AgentTask) -> Optional[str]:
        """为任务分配Agent"""
        async with self._lock:
            candidates = [
                a for a in self.agents.values()
                if a.state == AgentState.IDLE
                and (a.tenant_id is None or a.tenant_id == task.tenant_id)
            ]
            
            if not candidates:
                return None
            
            # 选择负载最低的Agent
            agent = min(candidates, key=lambda a: a.load_factor)
            
            agent.state = AgentState.BUSY
            agent.current_task = task.id
            agent.task_count += 1
            
            await self._persist_agent(agent)
            
            return agent.id
    
    async def release_agent(self, agent_id: str, success: bool = True):
        """释放Agent"""
        async with self._lock:
            if agent_id not in self.agents:
                return
            
            agent = self.agents[agent_id]
            agent.state = AgentState.IDLE
            agent.current_task = None
            
            if not success:
                agent.error_count += 1
            
            await self._persist_agent(agent)
    
    async def record_heartbeat(self, agent_id: str):
        """记录心跳"""
        if agent_id in self.agents:
            self.agents[agent_id].last_heartbeat = datetime.utcnow()
            await self._persist_agent(self.agents[agent_id])
    
    async def get_agent(self, agent_id: str) -> Optional[AgentInstance]:
        """获取Agent信息"""
        return self.agents.get(agent_id)
    
    async def get_available_agents(self, tenant_id: str = None) -> List[AgentInstance]:
        """获取可用Agent列表"""
        return [
            a for a in self.agents.values()
            if a.state == AgentState.IDLE
            and (tenant_id is None or a.tenant_id is None or a.tenant_id == tenant_id)
        ]
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取Agent池统计"""
        return {
            "total_agents": len(self.agents),
            "idle_agents": sum(1 for a in self.agents.values() if a.state == AgentState.IDLE),
            "busy_agents": sum(1 for a in self.agents.values() if a.state == AgentState.BUSY),
            "unhealthy_agents": sum(1 for a in self.agents.values() if a.state == AgentState.UNHEALTHY),
        }
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            await asyncio.sleep(self.health_check_interval)
            
            now = datetime.utcnow()
            timeout = self.health_check_interval * 3
            
            for agent_id, agent in list(self.agents.items()):
                elapsed = (now - agent.last_heartbeat).total_seconds()
                
                if elapsed > timeout and agent.state != AgentState.UNHEALTHY:
                    agent.state = AgentState.UNHEALTHY
                    await self._persist_agent(agent)
    
    async def _graceful_shutdown(self):
        """优雅关闭"""
        for agent_id in list(self.agents.keys()):
            await self.unregister_agent(agent_id, force=True)
    
    async def _persist_agent(self, agent: AgentInstance):
        """持久化Agent状态"""
        await self.redis.hset(
            f"agent:{agent.id}",
            mapping={
                "state": agent.state.value,
                "tenant_id": agent.tenant_id or "",
                "current_task": agent.current_task or "",
                "task_count": agent.task_count,
                "error_count": agent.error_count,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
            }
        )


# 全局实例
queue_manager: Optional[MultiTenantQueueManager] = None
agent_pool: Optional[AgentPoolManager] = None


async def init_distribution(redis_client: redis.Redis):
    """初始化分发系统"""
    global queue_manager, agent_pool
    queue_manager = MultiTenantQueueManager(redis_client)
    agent_pool = AgentPoolManager(redis_client)
    await agent_pool.start()


def get_queue_manager() -> Optional[MultiTenantQueueManager]:
    return queue_manager


def get_agent_pool() -> Optional[AgentPoolManager]:
    return agent_pool