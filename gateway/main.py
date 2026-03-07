"""
SmartLink Agent Management Platform - Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import uvicorn
import redis.asyncio as redis

from core.config import settings
from core.exceptions import SmartLinkException
from db import init_db, close_db
from gateway.api import api_router
from gateway.middleware.auth import AuthMiddleware
from gateway.middleware.logging import LoggingMiddleware
from gateway.middleware.rate_limit import RateLimitMiddleware
from gateway.websocket.manager import manager
from services.session_manager import session_manager
from agent.mcp.client import mcp_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    print(f"[START] Starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"   Environment: {settings.APP_ENV}")
    
    # Initialize database
    print("[DB] Initializing database...")
    await init_db()
    print("[OK] Database initialized")
    
    # Initialize Redis
    print("[REDIS] Connecting to Redis...")
    await manager.init_redis()
    print("[OK] Redis connected")
    
    # Initialize session manager
    print("[SESSION] Initializing session manager...")
    await session_manager.connect()
    print("[OK] Session manager initialized")
    
    print(f"[READY] {settings.APP_NAME} is ready!")
    
    yield
    
    # Shutdown
    print(f"[STOP] Shutting down {settings.APP_NAME}")
    
    # Close MCP connections
    await mcp_manager.disconnect_all()
    print("[OK] MCP connections closed")
    
    # Close session manager
    await session_manager.disconnect()
    print("[OK] Session manager closed")
    
    # Close Redis
    await manager.close()
    print("[OK] Redis connection closed")
    
    # Close database
    await close_db()
    print("[OK] Database connections closed")
    
    print("[BYE] Goodbye!")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    SmartLink Agent Management Platform Backend API
    
    ## Features
    
    - **Application Management**: Create, update, delete, and run AI agent applications
    - **Resource Management**: Manage Skills, MCP Servers, and Components
    - **WebSocket Support**: Real-time communication for agent execution
    - **Multi-LLM Support**: OpenAI, Anthropic Claude, and local models via LiteLLM
    - **MCP Protocol**: Support for Model Context Protocol
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware (order matters: last added = first executed)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)  # New auth middleware supporting JWT and API keys
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)


# Exception handlers
@app.exception_handler(SmartLinkException)
async def smartlink_exception_handler(request, exc: SmartLinkException):
    """Handle custom exceptions"""
    return JSONResponse(
        status_code=400,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions"""
    if settings.DEBUG:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "traceback": traceback.format_exc()
            }
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        }
    )


# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs": "/docs"
    }


def main():
    """Run the application"""
    uvicorn.run(
        "gateway.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()