"""
Database session management
Supports SQLite (development) and PostgreSQL (production)
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.config import settings

# Get database URL from settings
DATABASE_URL = settings.get_database_url()

# Determine if using SQLite (for pool settings)
is_sqlite = settings.DATABASE_TYPE == "sqlite"

# Create async engine with appropriate settings
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# SQLite doesn't support connection pooling
if not is_sqlite:
    engine_kwargs.update({
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


# Cache database (separate SQLite file for LLM response caching)
CACHE_DATABASE_URL = f"sqlite+aiosqlite:///./{settings.LLM_CACHE_DB}"

cache_engine = create_async_engine(
    CACHE_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

cache_session_maker = async_sessionmaker(
    cache_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_cache_db():
    """Initialize cache database - create cache table"""
    async with cache_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_cache_db():
    """Close cache database connections"""
    await cache_engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session
    Usage: 
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()