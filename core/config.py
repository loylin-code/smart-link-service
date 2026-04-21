"""
Core configuration management using Pydantic Settings
"""
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseType:
    """Database type constants"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Application
    APP_NAME: str = "SmartLink"
    APP_ENV: str = "development"
    DEBUG: bool = True
    VERSION: str = "1.0.0"
    API_BASE_URL: str = "http://localhost:8000"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_TYPE: str = Field(
        default="sqlite",
        description="Database type: 'sqlite' for development, 'postgresql' for production"
    )
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Database connection URL. If not set, will be constructed from other settings"
    )
    # SQLite settings (for development)
    SQLITE_DB_FILE: str = Field(
        default="smartlink.db",
        description="SQLite database file path (relative to project root)"
    )
    # PostgreSQL settings (for production)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "smartlink"
    
    # Database Connection Pool
    # Pool size: Number of persistent connections to maintain
    # Overflow: Additional connections allowed when pool is exhausted
    # Total max connections = pool_size + overflow
    # Recommended for production:
    #   - Low traffic: pool_size=10, overflow=5 (15 total)
    #   - Medium traffic: pool_size=20, overflow=10 (30 total) - DEFAULT
    #   - High traffic: pool_size=30, overflow=20 (50 total)
    # Note: Ensure PostgreSQL max_connections > your pool_size + overflow
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    def get_database_url(self) -> str:
        """
        Get database URL based on DATABASE_TYPE.
        - SQLite: sqlite+aiosqlite:///./{SQLITE_DB_FILE}
        - PostgreSQL: postgresql+asyncpg://user:pass@host:port/db
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        
        if self.DATABASE_TYPE == DatabaseType.SQLITE:
            return f"sqlite+aiosqlite:///./{self.SQLITE_DB_FILE}"
        else:
            return (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
    
    # Redis
    REDIS_URL: str = Field(
        ...,
        description="Redis connection URL"
    )
    # Redis Connection Pool
    # Max connections for Redis connection pool
    # Used for WebSocket pub/sub, session management, caching
    # Recommended for production:
    #   - Low traffic: 20-30 connections
    #   - Medium traffic: 50 connections - DEFAULT
    #   - High WebSocket concurrency: 100 connections
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    MASTER_API_KEY: str = Field(
        ...,
        description="Master API key for admin access"
    )
    SECRET_KEY: str = Field(
        ...,
        description="Secret key for JWT signing (min 32 chars)"
    )
    
    # JWT Settings
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth2 Provider 配置
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITLAB_CLIENT_ID: Optional[str] = None
    GITLAB_CLIENT_SECRET: Optional[str] = None

    # OAuth2 回调配置
    OAUTH_CALLBACK_BASE_URL: str = "http://localhost:8000/api/v1/auth/oauth"
    FRONTEND_URL: str = "http://localhost:5173"

    # OAuth2 安全配置
    OAUTH_STATE_EXPIRE_MINUTES: int = 10
    OAUTH_CLIENT_DEFAULT_EXPIRE_DAYS: int = 365
    
    # LLM
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for OpenAI or any OpenAI-compatible service (Bailian, DeepSeek, etc.)"
    )
    OPENAI_BASE_URL: Optional[str] = Field(
        default=None,
        description="Base URL for OpenAI API or compatible services. Example: https://coding.dashscope.aliyuncs.com/v1"
    )
    ANTHROPIC_API_KEY: Optional[str] = None
    
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
    
    # LLM Caching
    LLM_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable LLM response caching"
    )
    LLM_CACHE_TTL: int = Field(
        default=3600,
        description="Cache TTL in seconds (default: 1 hour)"
    )
    LLM_CACHE_DB: str = Field(
        default="cache.db",
        description="SQLite cache database file path"
    )

    # Agent Cache Configuration
    AGENT_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable agent config caching"
    )
    AGENT_CACHE_TTL: int = Field(
        default=3600,
        description="Agent config cache TTL in seconds (default: 1 hour)"
    )

    # LLM Retry Configuration
    LLM_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for LLM calls"
    )
    LLM_RETRY_BASE_DELAY: float = Field(
        default=1.0,
        description="Base delay for exponential backoff (seconds)"
    )
    LLM_RETRY_MAX_DELAY: float = Field(
        default=10.0,
        description="Maximum delay between retries (seconds)"
    )

    # MCP
    MCP_SERVERS_DIR: str = "./mcp_servers"
    MCP_SERVERS_URL: str = ""
    
    # CORS - Allow frontend development servers
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",  # Vite alternate
        "http://localhost:3000",  # React default
        "http://localhost:8080",  # Vue CLI default
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_TOKENS_PER_DAY: int = 100000
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # Logging Configuration
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level: DEBUG/INFO/WARNING/ERROR/CRITICAL"
    )
    LOG_FORMAT: str = Field(
        default="json",
        description="Log format: 'json' for structured, 'text' for plain"
    )
    LOG_DIR: str = Field(
        default="logs",
        description="Directory for log files"
    )
    LOG_STDOUT: bool = Field(
        default=True,
        description="Enable stdout logging (for container collection)"
    )
    LOG_FILE: bool = Field(
        default=True,
        description="Enable file logging"
    )
    LOG_MAX_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum log file size in bytes"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=5,
        description="Number of backup log files to keep"
    )

    # Session
    SESSION_EXPIRE_SECONDS: int = 86400  # 24 hours
    
    # Lane Concurrency
    MAX_CONCURRENT_LANES_PER_USER: int = 3
    
    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# Global settings instance
settings = Settings()