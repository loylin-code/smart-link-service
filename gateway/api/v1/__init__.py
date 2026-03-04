"""
API v1 module initialization
"""
from fastapi import APIRouter
from gateway.api.v1 import applications, resources, websocket

api_router = APIRouter()

# Include all API routes
api_router.include_router(
    applications.router,
    prefix="/applications",
    tags=["applications"]
)

api_router.include_router(
    resources.router,
    prefix="/resources",
    tags=["resources"]
)

api_router.include_router(
    websocket.router,
    tags=["websocket"]
)

__all__ = ["api_router"]