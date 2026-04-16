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

@pytest.fixture
async def async_session():
    """创建异步数据库会话用于测试"""
    from db.session import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession
    from auth.providers.state import OAuthState  # Import to register model
    from models.oauth import OAuthClient  # Import to register model
    
    # 使用内存 SQLite 进行测试
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with Session() as session:
        yield session
    
    await engine.dispose()
