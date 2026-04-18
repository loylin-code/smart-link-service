"""Tests for InterruptManager - execution cancellation support"""
import pytest
from agent.core.interrupt_manager import InterruptManager


class TestInterruptManager:
    """InterruptManager 测试"""

    @pytest.fixture
    def manager(self):
        """创建 InterruptManager 实例"""
        return InterruptManager()

    def test_register_and_unregister(self, manager):
        """测试注册和取消注册执行"""
        execution_id = "exec-001"
        
        # 注册执行
        manager.register(execution_id)
        assert execution_id in manager._local_executions
        
        # 取消注册
        manager.unregister(execution_id)
        assert execution_id not in manager._local_executions

    def test_cancel_local_execution(self, manager):
        """测试取消本地执行"""
        execution_id = "exec-002"
        
        # 注册执行
        manager.register(execution_id)
        
        # 取消执行
        result = manager.cancel(execution_id)
        
        assert result["status"] == "cancelled"
        assert "cancelled_at" in result
        assert isinstance(result["cancelled_at"], int)
        # 验证取消事件已触发
        assert manager.is_cancelled(execution_id)

    def test_cancel_not_found(self, manager):
        """测试取消不存在的执行"""
        result = manager.cancel("non-existent-exec")
        
        assert result["status"] == "not_found"

    def test_is_cancelled_false(self, manager):
        """测试未取消的执行"""
        execution_id = "exec-003"
        
        manager.register(execution_id)
        assert not manager.is_cancelled(execution_id)

    def test_is_cancelled_true(self, manager):
        """测试已取消的执行"""
        execution_id = "exec-004"
        
        manager.register(execution_id)
        manager.cancel(execution_id)
        assert manager.is_cancelled(execution_id)

    def test_cancelled_at_timestamp(self, manager):
        """测试 cancelled_at 时间戳"""
        execution_id = "exec-005"
        
        manager.register(execution_id)
        result = manager.cancel(execution_id)
        
        # 时间戳应该是毫秒级整数
        assert isinstance(result["cancelled_at"], int)
        # 时间戳应该接近当前时间（允许 1 秒误差）
        import time
        current_ms = int(time.time() * 1000)
        assert abs(result["cancelled_at"] - current_ms) < 1000

    def test_list_active_executions(self, manager):
        """测试列出活跃执行"""
        manager.register("exec-001")
        manager.register("exec-002")
        manager.register("exec-003")
        
        active = manager.list_active_executions()
        
        assert "exec-001" in active
        assert "exec-002" in active
        assert "exec-003" in active
        assert len(active) == 3
        
        # 取消一个后检查
        manager.cancel("exec-002")
        active = manager.list_active_executions()
        assert "exec-002" not in active
        assert len(active) == 2

    def test_unregister_non_existent(self, manager):
        """测试取消注册不存在的执行（不应报错）"""
        # 不应该抛出异常
        manager.unregister("non-existent")
