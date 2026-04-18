"""Execution Interrupt Manager - supports HTTP and WebSocket cancellation"""
import asyncio
import time
from typing import Dict, List, Optional


class InterruptManager:
    """
    执行中断管理器
    
    支持本地执行取消，Phase 2 可扩展 Redis 分布式支持。
    用于 HTTP DELETE 取消和 WebSocket cancel 消息。
    """

    def __init__(self):
        """初始化中断管理器"""
        self._local_executions: dict[str, asyncio.Event] = {}
        self._cancel_events: dict[str, int] = {}
        self._redis: object | None = None  # Phase 2 预留

    def register(self, execution_id: str) -> None:
        """
        注册执行
        
        Args:
            execution_id: 执行 ID
        """
        self._local_executions[execution_id] = asyncio.Event()

    def unregister(self, execution_id: str) -> None:
        """
        取消注册执行
        
        Args:
            execution_id: 执行 ID
        """
        self._local_executions.pop(execution_id, None)
        self._cancel_events.pop(execution_id, None)

    def cancel(self, execution_id: str) -> dict[str, int]:
        """
        取消执行
        
        Args:
            execution_id: 执行 ID
            
        Returns:
            {"status": "cancelled", "cancelled_at": timestamp} 或
            {"status": "not_found"}
        """
        if execution_id not in self._local_executions:
            return {"status": "not_found"}

        # 触发取消事件
        self._local_executions[execution_id].set()
        # 记录取消时间戳 (毫秒)
        cancelled_at = int(time.time() * 1000)
        self._cancel_events[execution_id] = cancelled_at

        return {"status": "cancelled", "cancelled_at": cancelled_at}

    def is_cancelled(self, execution_id: str) -> bool:
        """
        检查执行是否已取消
        
        Args:
            execution_id: 执行 ID
            
        Returns:
            True if cancelled, False otherwise
        """
        if execution_id not in self._local_executions:
            return False
        return self._local_executions[execution_id].is_set()

    def get_cancel_event(self, execution_id: str) -> Optional[asyncio.Event]:
        """
        获取取消事件
        
        Args:
            execution_id: 执行 ID
            
        Returns:
            asyncio.Event or None if not found
        """
        return self._local_executions.get(execution_id)

    def list_active_executions(self) -> list[str]:
        """
        列出活跃执行 ID
        
        Returns:
            未取消的执行 ID 列表
        """
        return [
            exec_id for exec_id, event in self._local_executions.items()
            if not event.is_set()
        ]

    async def listen_for_cancel(self, execution_id: str) -> bool:
        """
        监听取消事件（Phase 2 实现 Redis 支持）
        
        Args:
            execution_id: 执行 ID
            
        Returns:
            True if cancelled, False otherwise
        """
        # Phase 2: 实现 Redis pub/sub 监听
        # 当前仅支持本地取消事件
        if execution_id not in self._local_executions:
            return False
        
        await self._local_executions[execution_id].wait()
        return True
