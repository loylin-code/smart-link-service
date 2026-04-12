"""pytest 配置文件"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_settings():
    """Mock 配置"""
    mock = MagicMock()
    mock.OPENAI_API_KEY = "test-api-key"
    mock.DEFAULT_LLM_MODEL = "gpt-4"
    mock.DATABASE_URL = "sqlite:///test.db"
    return mock

@pytest.fixture
def mock_db_session():
    """Mock 数据库会话"""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    return mock
