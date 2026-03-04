"""
Core configuration management using Pydantic Settings
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection URL with asyncpg driver"
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = Field(
        ...,
        description="Redis connection URL"
    )
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    MASTER_API_KEY: str = Field(
        ...,
        description="Master API key for admin access"
    )
    SECRET_KEY: str = Field(
        ...,
        description="Secret key for JWT signing"
    )
    
    # LLM
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o"
    
    # MCP
    MCP_SERVERS_DIR: str = "./mcp_servers"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# Global settings instance
settings = Settings()