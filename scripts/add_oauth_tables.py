"""Add OAuth2 tables migration script"""
import asyncio
import argparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def migrate(database_url: str) -> None:
    """Create OAuth2 tables"""
    engine = create_async_engine(database_url)
    
    async with engine.begin() as conn:
        # 1. 创建 oauth_states 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                id VARCHAR(64) PRIMARY KEY,
                state VARCHAR(64) UNIQUE NOT NULL,
                provider VARCHAR(32) NOT NULL,
                redirect_uri VARCHAR(512) NOT NULL,
                tenant_id VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """))
        
        # 2. 创建 oauth_clients 表
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS oauth_clients (
                id VARCHAR(64) PRIMARY KEY,
                tenant_id VARCHAR(64) NOT NULL,
                client_id VARCHAR(64) UNIQUE NOT NULL,
                secret_hash VARCHAR(64) NOT NULL,
                name VARCHAR(255) NOT NULL,
                allowed_scopes VARCHAR(1024) DEFAULT '[]',
                is_active BOOLEAN DEFAULT TRUE,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                total_requests INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 3. 创建索引
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_oauth_states_expires 
            ON oauth_states (expires_at)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_oauth_clients_tenant 
            ON oauth_clients (tenant_id)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_oauth_clients_client_id 
            ON oauth_clients (client_id)
        """))
    
    await engine.dispose()
    print("OAuth2 tables created successfully")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default="sqlite+aiosqlite:///./smartlink.db",
        help="Database URL"
    )
    args = parser.parse_args()
    
    asyncio.run(migrate(args.database_url))

if __name__ == "__main__":
    main()
