"""
API v1 module initialization
"""
from fastapi import APIRouter
from gateway.api.v1 import applications, resources, websocket, auth, conversations, agents, mcp_servers, agent_design

api_router = APIRouter()

# Authentication routes (no prefix, mounted at /auth)
api_router.include_router(
    auth.router,
    tags=["Authentication"]
)

# Include all API routes
api_router.include_router(
    agents.router,
    tags=["Agents"]
)

api_router.include_router(
    applications.router,
    prefix="/applications",
    tags=["Applications"]
)

api_router.include_router(
    resources.router,
    prefix="/resources",
    tags=["Resources"]
)

api_router.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"]
)

api_router.include_router(
    websocket.router,
    tags=["WebSocket"]
)

api_router.include_router(
    mcp_servers.router,
    prefix="/mcp-servers",
    tags=["MCP Servers"]
)

api_router.include_router(
    agent_design.router,
    prefix="/agent-design",
    tags=["Agent Design"]
)