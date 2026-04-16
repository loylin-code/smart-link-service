"""OAuth State Manager 单元测试"""
import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestOAuthState:
    """OAuthState 模型测试"""

    @pytest.mark.asyncio
    async def test_create_state(self, async_session):
        """测试创建 state - 验证 state 格式和数据库操作"""
        from auth.providers.state import StateManager
        
        manager = StateManager(async_session)
        state_record = await manager.create_state(
            provider="google",
            redirect_uri="http://localhost:8000/callback",
            tenant_id="tenant-123"
        )
        
        # 验证 state 格式 (secrets.token_urlsafe(32) 生成)
        assert state_record.state is not None
        assert len(state_record.state) >= 40  # token_urlsafe(32) 生成约 43 字符
        
        # 验证字段
        assert state_record.provider == "google"
        assert state_record.redirect_uri == "http://localhost:8000/callback"
        assert state_record.tenant_id == "tenant-123"
        
        # 验证过期时间 (10 分钟后)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assert state_record.expires_at > now
        expected_expiry = now + timedelta(minutes=10)
        assert abs((state_record.expires_at - expected_expiry).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_validate_state_success(self, async_session):
        """测试成功验证 state"""
        from auth.providers.state import StateManager
        
        manager = StateManager(async_session)
        state_record = await manager.create_state(
            provider="github",
            redirect_uri="http://localhost:8000/callback",
            tenant_id="tenant-456"
        )
        
        # 验证 state
        validated = await manager.validate_state(state_record.state)
        
        assert validated is not None
        assert validated.state == state_record.state
        assert validated.provider == "github"
        
        # 验证 state 已被删除 (一次性使用)
        validated_again = await manager.validate_state(state_record.state)
        assert validated_again is None

    @pytest.mark.asyncio
    async def test_validate_state_expired(self, async_session):
        """测试过期 state 返回 None"""
        from auth.providers.state import StateManager
        from auth.providers.state import OAuthState
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # 创建已过期的 state
        expired_state = OAuthState(
            state="expired_test_state_12345",
            provider="google",
            redirect_uri="http://localhost:8000/callback",
            tenant_id="tenant-789",
            created_at=now - timedelta(minutes=15),
            expires_at=now - timedelta(minutes=5)  # 已过期 5 分钟
        )
        
        async_session.add(expired_state)
        await async_session.commit()
        
        manager = StateManager(async_session)
        validated = await manager.validate_state("expired_test_state_12345")
        
        # 过期的 state 应该返回 None
        assert validated is None

    @pytest.mark.asyncio
    async def test_validate_state_not_found(self, async_session):
        """测试不存在的 state 返回 None"""
        from auth.providers.state import StateManager
        
        manager = StateManager(async_session)
        validated = await manager.validate_state("nonexistent_state_xyz")
        
        # 不存在的 state 应该返回 None
        assert validated is None
