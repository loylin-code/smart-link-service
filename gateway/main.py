"""
SmartLink Agent Management Platform - Main Application
"""
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY
import uvicorn
import redis.asyncio as redis
import yaml
import os
from sqlalchemy import select

from core.config import settings
from core.exceptions import SmartLinkException
from db import init_db, close_db, async_session_maker
from gateway.api import api_router
from gateway.middleware.auth import AuthMiddleware
from gateway.middleware.logging import LoggingMiddleware
from gateway.middleware.rate_limit import RateLimitMiddleware
from gateway.middleware.request_id import RequestIDMiddleware
from gateway.middleware.metrics import MetricsMiddleware
from gateway.websocket.manager import manager
from gateway.websocket.lane import init_lane_registry
from gateway.websocket.router import init_router
from gateway.websocket.heartbeat import init_heartbeat_manager
from services.session_manager import session_manager
from agent.mcp.client import mcp_manager
from agent.distribution import init_distribution
from agent.llm.resolver import init_model_resolver
from agent.agentscope.toolkit import AgentToolkit
from models.application import MCPServer, ResourceStatus


async def load_mcp_servers() -> AgentToolkit:
    """
    Load MCP servers on application startup from 3 sources:
    1. Database (MCPServer table with ACTIVE status)
    2. Config file (config/mcp_servers.yml)
    3. Environment variable (MCP_SERVERS_URL comma-separated)
    
    Returns:
        AgentToolkit with registered MCP servers
    """
    toolkit = AgentToolkit()
    
    async with async_session_maker() as session:
        # 1. Load from database
        print("[MCP] Loading MCP servers from database...")
        db_servers = await session.execute(
            select(MCPServer).where(MCPServer.status == ResourceStatus.ACTIVE)
        )
        
        for server in db_servers.scalars().all():
            try:
                # Build config from database
                config = {
                    "name": str(server.name),
                    "type": str(server.type) if server.type else "stdio",
                    **(server.config or {})
                }
                if server.endpoint:
                    config["endpoint"] = str(server.endpoint)
                
                # Register with MCP manager
                client = await mcp_manager.register_client(str(server.name), config)
                
                # Register with toolkit
                await toolkit.register_mcp_server(client)
                print(f"[MCP] Registered: {server.name} (database)")
            except Exception as e:
                # Update server status to INACTIVE
                try:
                    server.status = ResourceStatus.INACTIVE  # type: ignore
                    await session.flush()
                except Exception:
                    pass  # Ignore update error, continue with other servers
                print(f"[MCP] Failed to register {server.name}: {str(e)[:100]}")
        
        # 2. Load from config file
        config_file = os.path.join(os.getcwd(), "config", "mcp_servers.yml")
        if os.path.exists(config_file):
            print(f"[MCP] Loading MCP servers from {config_file}...")
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                
                if config_data and 'mcp_servers' in config_data:
                    for server_config in config_data['mcp_servers']:
                        if not server_config:  # Skip commented out entries
                            continue
                        
                        name = server_config.get('name', 'unknown')
                        try:
                            # Register with MCP manager
                            client = await mcp_manager.register_client(name, server_config)
                            
                            # Register with toolkit
                            await toolkit.register_mcp_server(client)
                            print(f"[MCP] Registered: {name} (config file)")
                        except Exception as e:
                            print(f"[MCP] Failed to register {name}: {str(e)[:100]}")
            except Exception as e:
                print(f"[MCP] Error reading config file: {str(e)[:100]}")
        
        # 3. Load from environment variable
        env_urls = settings.MCP_SERVERS_URL
        if env_urls:
            print("[MCP] Loading MCP servers from environment...")
            for url in env_urls.split(','):
                url = url.strip()
                if not url:
                    continue
                
                name = url.split('/')[-1] or 'unknown'
                try:
                    config = {
                        "name": name,
                        "type": "http",
                        "endpoint": url
                    }
                    
                    # Register with MCP manager
                    client = await mcp_manager.register_client(name, config)
                    
                    # Register with toolkit
                    await toolkit.register_mcp_server(client)
                    print(f"[MCP] Registered: {name} (environment)")
                except Exception as e:
                    print(f"[MCP] Failed to register {name}: {str(e)[:100]}")
    
    return toolkit


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
    
    # Initialize Redis (optional in development mode)
    redis_client = None
    print("[REDIS] Connecting to Redis...")
    try:
        await manager.init_redis()
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        print("[OK] Redis connected")
    except Exception as e:
        if settings.is_development:
            print(f"[WARN] Redis connection failed (development mode, continuing without Redis): {str(e)[:100]}")
        else:
            raise
    
    # Initialize session manager (skip if no Redis)
    if redis_client:
        print("[SESSION] Initializing session manager...")
        await session_manager.connect()
        print("[OK] Session manager initialized")
        
        # Initialize Lane Manager registry
        print("[LANE] Initializing lane manager...")
        await init_lane_registry(redis_client)
        print("[OK] Lane manager initialized")
        
        # Initialize request router
        print("[ROUTER] Initializing request router...")
        await init_router(redis_client)
        print("[OK] Request router initialized")
        
        # Initialize heartbeat manager
        print("[HEARTBEAT] Initializing heartbeat manager...")
        await init_heartbeat_manager(redis_client)
        print("[OK] Heartbeat manager initialized")
        
        # Initialize distribution system (task queue + agent pool)
        print("[DISTRIBUTION] Initializing distribution system...")
        await init_distribution(redis_client)
        print("[OK] Distribution system initialized")
    else:
        print("[WARN] Skipping Redis-dependent services (no Redis connection)")
    
    # Initialize model resolver
    print("[MODEL] Initializing model resolver...")
    init_model_resolver()
    print("[OK] Model resolver initialized")
    
    # Load MCP servers
    print("[MCP] Loading MCP servers...")
    toolkit = await load_mcp_servers()
    app.state.toolkit = toolkit
    print("[OK] MCP servers loaded")
    
    print(f"[READY] {settings.APP_NAME} is ready!")
    
    yield
    
    # Shutdown
    print(f"[STOP] Shutting down {settings.APP_NAME}")
    
    # Close MCP connections
    await mcp_manager.disconnect_all()
    print("[OK] MCP connections closed")
    
    # Close session manager
    if redis_client:
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
    - **Lane Concurrency**: Per-user concurrent execution with 3 lanes
    - **Task Queue**: Priority-based task distribution
    - **Agent Pool**: Instance management and load balancing
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

# Add custom middleware (order matters: first added = last executed)
app.add_middleware(MetricsMiddleware)  # Prometheus metrics collection
app.add_middleware(RequestIDMiddleware)  # Generates request_id
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)


# Exception handlers
@app.exception_handler(SmartLinkException)
async def smartlink_exception_handler(request: Request, exc: SmartLinkException):
    """Handle custom exceptions with proper HTTP status codes"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "requestId": getattr(request.state, "request_id", "unknown"),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTPExceptions with unified format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "details": {},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "requestId": getattr(request.state, "request_id", "unknown"),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log the error with request context
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(
        f"Unexpected error: {exc}",
        extra={
            "request_id": request_id,
            "path": str(request.url.path)
        }
    )
    
    if settings.DEBUG:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "details": {"traceback": traceback.format_exc()},
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "requestId": request_id,
                "path": str(request.url.path)
            }
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "requestId": request_id,
            "path": str(request.url.path)
        }
    )


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    No authentication required (standard Prometheus practice).
    """
    metrics_output = generate_latest(REGISTRY)
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
        headers={"Cache-Control": "no-cache"}
    )


# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from gateway.websocket.lane import get_lane_registry
    from agent.distribution import get_queue_manager, get_agent_pool
    
    stats = {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV
    }
    
    # Add system stats
    lane_registry = get_lane_registry()
    if lane_registry:
        stats["lane_stats"] = jsonable_encoder(lane_registry.get_global_stats())
    
    queue_manager = get_queue_manager()
    if queue_manager:
        stats["queue_stats"] = await queue_manager.get_global_stats()
    
    agent_pool = get_agent_pool()
    if agent_pool:
        stats["agent_stats"] = await agent_pool.get_stats()
    
    return stats


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