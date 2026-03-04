"""
Database initialization script
"""
import asyncio
from db.session import init_db, close_db


async def main():
    """Initialize database"""
    print("Initializing database...")
    
    try:
        await init_db()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())