"""
Agent API Routes - /smart-link-service/api/v1/agents
Based on architecture design document and frontend services/agent.ts
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.agent import AgentStatus, AgentType
from schemas.common import ApiResponse, PaginatedData
from schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListParams,
    AgentRuntimeStatusResponse,
    agent_to_response
)
from services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=ApiResponse[PaginatedData])
async def list_agents(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="Page size"),
    status: Optional[AgentStatus] = Query(default=None, description="Filter by status"),
    type: Optional[AgentType] = Query(default=None, description="Filter by type"),
    keyword: Optional[str] = Query(default=None, description="Search keyword"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get agent list with pagination
    
    Frontend: GET /api/v1/agents/?page=1&page_size=20&status=active&type=custom&keyword=客服
    """
    # Get tenant_id from request context (set by auth middleware)
    tenant_context = getattr(request.state, "tenant_context", None)
    
    # For master key, get first tenant from database
    if tenant_context and tenant_context.is_master:
        from sqlalchemy import select
        from models import Tenant, TenantStatus
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        tenant_id = tenant.id if tenant else "default"
    else:
        tenant_id = tenant_context.tenant_id if tenant_context else "default"
    
    result = await AgentService.list_agents(
        db=db,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        status=status,
        type=type,
        keyword=keyword,
        category=category
    )
    
    # Convert agents to response format
    result.list = [agent_to_response(agent) for agent in result.list]
    
    return ApiResponse(data=result)


@router.post("", response_model=ApiResponse[AgentResponse], status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new agent
    
    Frontend: POST /api/v1/agents/
    """
    # Get tenant_id and user_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    user_id = tenant_context.user_id if tenant_context else None
    
    # For master key, get first tenant from database
    if tenant_context and tenant_context.is_master:
        from sqlalchemy import select
        from models import Tenant, TenantStatus
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active tenant found"
            )
        tenant_id = tenant.id
    else:
        tenant_id = tenant_context.tenant_id if tenant_context else None
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant ID is required"
        )
    
    # Check if code already exists
    existing = await AgentService.get_agent_by_code(db, tenant_id, data.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with code '{data.code}' already exists"
        )
    
    agent = await AgentService.create_agent(
        db=db,
        tenant_id=tenant_id,
        data=data,
        user_id=user_id
    )
    
    return ApiResponse(data=agent_to_response(agent))


@router.get("/{agent_id}", response_model=ApiResponse[AgentResponse])
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get agent by ID
    
    Frontend: GET /smart-link-service/api/v1/agents/{id}
    """
    agent = await AgentService.get_agent_by_id(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(agent))


@router.put("/{agent_id}", response_model=ApiResponse[AgentResponse])
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update agent
    
    Frontend: PUT /api/v1/agents/{id}
    """
    agent = await AgentService.update_agent(db, agent_id, data)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(agent))


@router.delete("/{agent_id}", response_model=ApiResponse[bool])
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete agent
    
    Frontend: DELETE /smart-link-service/api/v1/agents/{id}
    """
    # Only allow deletion of draft agents
    agent = await AgentService.get_agent_by_id(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    if agent.status != AgentStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete agents in draft status"
        )
    
    success = await AgentService.delete_agent(db, agent_id)
    return ApiResponse(data=success)


@router.post("/{agent_id}/activate", response_model=ApiResponse[AgentResponse])
async def activate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Activate agent (change status to ACTIVE)
    
    Frontend: POST /api/v1/agents/{id}/activate
    """
    agent = await AgentService.activate_agent(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(agent))


@router.post("/{agent_id}/pause", response_model=ApiResponse[AgentResponse])
async def pause_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Pause agent (change status to PAUSED)
    
    Frontend: POST /api/v1/agents/{id}/pause
    """
    agent = await AgentService.pause_agent(db, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(agent))


@router.put("/{agent_id}/capabilities", response_model=ApiResponse[AgentResponse])
async def update_capabilities(
    agent_id: str,
    capabilities: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Update agent capabilities configuration
    
    Frontend: PUT /api/v1/agents/{id}/capabilities
    """
    agent = await AgentService.update_capabilities(db, agent_id, capabilities)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(agent))


@router.put("/{agent_id}/knowledge", response_model=ApiResponse[AgentResponse])
async def update_knowledge(
    agent_id: str,
    knowledge: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Update agent knowledge configuration
    
    Frontend: PUT /api/v1/agents/{id}/knowledge
    """
    agent = await AgentService.update_knowledge(db, agent_id, knowledge)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(agent))


@router.get("/runtime/status", response_model=ApiResponse[list])
async def get_runtime_status(
    db: AsyncSession = Depends(get_db)
):
    """
    Get runtime status for active agents
    
    Frontend: GET /api/v1/agents/runtime/status (derived from getRuntimeStatus)
    """
    # TODO: Implement actual runtime status tracking
    # For now, return empty list
    return ApiResponse(data=[])


@router.post("/{agent_id}/duplicate", response_model=ApiResponse[AgentResponse])
async def duplicate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Duplicate an agent
    
    Note: This is a convenience endpoint, frontend uses create with original data
    """
    # TODO: Get tenant_id and user_id from auth context
    tenant_id = "default"
    user_id = None
    
    new_agent = await AgentService.duplicate_agent(db, agent_id, tenant_id, user_id)
    if not new_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found"
        )
    
    return ApiResponse(data=agent_to_response(new_agent))