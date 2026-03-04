"""
SmartLink Agent Management Platform - Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import uvicorn

from core.config import settings
from core.exceptions import SmartLinkException
from db import init_db, close_db
from gateway.api import api_router
from gateway.middleware import APIKeyMiddleware, LoggingMiddleware
from gateway.websocket.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"   Environment: {settings.APP_ENV}")
    
    # Initialize database
    print("📦 Initializing database...")
    await init_db()
    print("✓ Database initialized")
    
    # Initialize Redis
    print("🔴 Connecting to Redis...")
    await manager.init_redis()
    print("✓ Redis connected")
    
    print(f"✅ {settings.APP_NAME} is ready!")
    
    yield
    
    # Shutdown
    print(f"🛑 Shutting down {settings.APP_NAME}")
    
    # Close Redis
    await manager.close()
    print("✓ Redis connection closed")
    
    # Close database
    await close_db()
    print("✓ Database connections closed")
    
    print("👋 Goodbye!")


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

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(APIKeyMiddleware)


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