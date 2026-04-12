"""
API v1 module initialization
"""
from fastapi import APIRouter
from gateway.api.v1 import applications, resources, websocket, auth, conversations, agents

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