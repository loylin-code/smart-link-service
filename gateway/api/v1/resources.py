"""
API routes for resource management (Skills, MCP, Components)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.common import (
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerResponse,
    ResponseBase,
    PaginatedResponse
)
from services.resource_service import ResourceService
from models.application import ResourceStatus

router = APIRouter()


# ============================================================
# Skills endpoints
# ============================================================

@router.get("/skills", response_model=PaginatedResponse)
async def list_skills(
    page: int = 1,
    page_size: int = 20,
    status: Optional[ResourceStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all skills"""
    service = ResourceService(db)
    skills, total = await service.list_skills(page, page_size, status)
    
    return PaginatedResponse(
        code=200,
        message="success",
        total=total,
        page=page,
        page_size=page_size,
        data=[SkillResponse.from_orm(skill) for skill in skills]
    )


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    skill_data: SkillCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new skill"""
    service = ResourceService(db)
    skill = await service.create_skill(skill_data)
    
    return SkillResponse.from_orm(skill)


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get skill by ID"""
    service = ResourceService(db)
    skill = await service.get_skill(skill_id)
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found"
        )
    
    return SkillResponse.from_orm(skill)


@router.put("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    skill_data: SkillUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update skill"""
    service = ResourceService(db)
    skill = await service.update_skill(skill_id, skill_data)
    
    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found"
        )
    
    return SkillResponse.from_orm(skill)


@router.delete("/skills/{skill_id}", response_model=ResponseBase)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete skill"""
    service = ResourceService(db)
    success = await service.delete_skill(skill_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id} not found"
        )
    
    return ResponseBase(code=200, message="Skill deleted successfully")


# ============================================================
# MCP Server endpoints
# ============================================================

@router.get("/mcp", response_model=PaginatedResponse)
async def list_mcp_servers(
    page: int = 1,
    page_size: int = 20,
    status: Optional[ResourceStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all MCP servers"""
    service = ResourceService(db)
    servers, total = await service.list_mcp_servers(page, page_size, status)
    
    return PaginatedResponse(
        code=200,
        message="success",
        total=total,
        page=page,
        page_size=page_size,
        data=[MCPServerResponse.from_orm(server) for server in servers]
    )


@router.post("/mcp", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    server_data: MCPServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new MCP server"""
    service = ResourceService(db)
    server = await service.create_mcp_server(server_data)
    
    return MCPServerResponse.from_orm(server)


@router.get("/mcp/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get MCP server by ID"""
    service = ResourceService(db)
    server = await service.get_mcp_server(server_id)
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Server {server_id} not found"
        )
    
    return MCPServerResponse.from_orm(server)


@router.put("/mcp/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    server_data: MCPServerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update MCP server"""
    service = ResourceService(db)
    server = await service.update_mcp_server(server_id, server_data)
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Server {server_id} not found"
        )
    
    return MCPServerResponse.from_orm(server)


@router.delete("/mcp/{server_id}", response_model=ResponseBase)
async def delete_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete MCP server"""
    service = ResourceService(db)
    success = await service.delete_mcp_server(server_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Server {server_id} not found"
        )
    
    return ResponseBase(code=200, message="MCP Server deleted successfully")


# ============================================================
# Component endpoints (for frontend component management)
# ============================================================

@router.get("/components")
async def list_components(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List all frontend components"""
    service = ResourceService(db)
    components, total = await service.list_components(page, page_size)
    
    return {
        "code": 200,
        "message": "success",
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": components
    }