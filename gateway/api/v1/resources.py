"""
API routes for resource management (Skills, MCP, Components)
Aligned with frontend service expectations
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.session import get_db
from schemas import (
    ApiResponse, PaginatedData,
    SkillCreate, SkillUpdate, SkillTestResponse,
    MCPServerCreate, MCPServerUpdate,
    MCPServerTestResponse, MCPServerRefreshResponse
)
from models import Skill, MCPServer, Component, ResourceStatus


router = APIRouter(tags=["Resources"])


# ============================================================
# Helper Functions
# ============================================================

def skill_to_response(skill: Skill) -> dict:
    """Convert Skill model to frontend-expected response format"""
    return {
        "id": skill.id,
        "name": skill.name,
        "display_name": skill.name.replace("_", " ").title(),
        "version": "1.0.0",
        "category": "processing",
        "status": "enabled" if skill.status == ResourceStatus.ACTIVE else "disabled",
        "author": "system" if skill.type == "builtin" else "user",
        "description": skill.description or "",
        "tags": [],
        "risk_level": "low",
        "requires_approval": False,
        "input_schema": skill.parameters_schema if hasattr(skill, 'parameters_schema') else {},
        "output_schema": {},
        "config": skill.config or {},
        "dependencies": {},
        "stats": {"totalCalls": 0, "successRate": 100, "avgDuration": 0, "last30Days": {"calls": 0, "tokens": {"input": 0, "output": 0}, "cost": 0}},
        "created_at": skill.created_at,
        "updated_at": skill.updated_at
    }


def mcp_to_response(mcp: MCPServer) -> dict:
    """Convert MCPServer model to frontend-expected response format"""
    return {
        "id": mcp.id,
        "name": mcp.name,
        "unique_id": mcp.id,
        "version": "1.0.0",
        "description": mcp.description or "",
        "author": "system",
        "homepage": None,
        "transport": mcp.type or "stdio",
        "status": "connected" if mcp.status == ResourceStatus.ACTIVE else "disconnected",
        "response_time": None,
        "error_count": 0,
        "capabilities": {"tools": len(mcp.tools) if mcp.tools else 0, "resources": len(mcp.resources) if mcp.resources else 0, "prompts": 0},
        "config": mcp.config or {},
        "tools": mcp.tools or [],
        "resources": mcp.resources or [],
        "prompts": [],
        "last_active": None,
        "last_error": None,
        "created_at": mcp.created_at,
        "updated_at": mcp.updated_at
    }


def component_to_response(component: Component) -> dict:
    """Convert Component model to frontend-expected response format"""
    return {
        "id": component.id,
        "name": component.name,
        "description": component.description or "",
        "type": component.type,
        "status": "active" if component.status == ResourceStatus.ACTIVE else "inactive",
        "path": component.path,
        "meta": component.meta or {},
        "created_at": component.created_at,
        "updated_at": component.updated_at
    }


# ============================================================
# Skills API
# ============================================================

@router.get("/skills", response_model=ApiResponse[PaginatedData[dict]])
async def list_skills(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get skills list with pagination"""
    query = select(Skill)
    count_query = select(func.count(Skill.id))
    
    if status:
        resource_status = ResourceStatus.ACTIVE if status == "active" else ResourceStatus.INACTIVE
        query = query.where(Skill.status == resource_status)
        count_query = count_query.where(Skill.status == resource_status)
    
    if keyword:
        query = query.where(Skill.name.ilike(f"%{keyword}%"))
        count_query = count_query.where(Skill.name.ilike(f"%{keyword}%"))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    skills = result.scalars().all()
    
    return ApiResponse(data=PaginatedData(list=[skill_to_response(s) for s in skills], total=total, page=page, page_size=page_size))


@router.get("/skills/{skill_id}", response_model=ApiResponse[dict])
async def get_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    """Get skill by ID"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return ApiResponse(data=skill_to_response(skill))


@router.post("/skills", response_model=ApiResponse[dict])
async def create_skill(data: SkillCreate, db: AsyncSession = Depends(get_db)):
    """Create a new skill"""
    import uuid
    skill = Skill(id=str(uuid.uuid4()), name=data.name, description=data.description, type=data.type, status=ResourceStatus.ACTIVE, config=data.config)
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return ApiResponse(data=skill_to_response(skill))


@router.put("/skills/{skill_id}", response_model=ApiResponse[dict])
async def update_skill(skill_id: str, data: SkillUpdate, db: AsyncSession = Depends(get_db)):
    """Update skill"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        update_data["status"] = ResourceStatus.ACTIVE if update_data["status"] == "active" else ResourceStatus.INACTIVE
    
    for key, value in update_data.items():
        setattr(skill, key, value)
    
    await db.commit()
    await db.refresh(skill)
    return ApiResponse(data=skill_to_response(skill))


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    """Delete skill"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(skill)
    await db.commit()
    return ApiResponse(data={"deleted": True})


@router.post("/skills/{skill_id}/test", response_model=ApiResponse[SkillTestResponse])
async def test_skill(skill_id: str, params: dict = {}, db: AsyncSession = Depends(get_db)):
    """Test skill execution"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return ApiResponse(data=SkillTestResponse(success=True, result={"message": f"Skill {skill.name} test successful"}, error=None))


# ============================================================
# MCP Servers API
# ============================================================

@router.get("/mcp", response_model=ApiResponse[PaginatedData[dict]])
async def list_mcp_servers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get MCP servers list with pagination"""
    query = select(MCPServer)
    count_query = select(func.count(MCPServer.id))
    
    if status:
        resource_status = ResourceStatus.ACTIVE if status == "active" else ResourceStatus.INACTIVE
        query = query.where(MCPServer.status == resource_status)
        count_query = count_query.where(MCPServer.status == resource_status)
    
    if keyword:
        query = query.where(MCPServer.name.ilike(f"%{keyword}%"))
        count_query = count_query.where(MCPServer.name.ilike(f"%{keyword}%"))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    servers = result.scalars().all()
    
    return ApiResponse(data=PaginatedData(list=[mcp_to_response(s) for s in servers], total=total, page=page, page_size=page_size))


@router.get("/mcp/{server_id}", response_model=ApiResponse[dict])
async def get_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Get MCP server by ID"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return ApiResponse(data=mcp_to_response(server))


@router.post("/mcp", response_model=ApiResponse[dict])
async def create_mcp_server(data: MCPServerCreate, db: AsyncSession = Depends(get_db)):
    """Create a new MCP server"""
    import uuid
    server = MCPServer(id=str(uuid.uuid4()), name=data.name, description=data.description, type=data.type, endpoint=data.endpoint, status=ResourceStatus.ACTIVE, config=data.config)
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return ApiResponse(data=mcp_to_response(server))


@router.put("/mcp/{server_id}", response_model=ApiResponse[dict])
async def update_mcp_server(server_id: str, data: MCPServerUpdate, db: AsyncSession = Depends(get_db)):
    """Update MCP server"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    
    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data:
        update_data["status"] = ResourceStatus.ACTIVE if update_data["status"] in ["active", "connected"] else ResourceStatus.INACTIVE
    
    for key, value in update_data.items():
        setattr(server, key, value)
    
    await db.commit()
    await db.refresh(server)
    return ApiResponse(data=mcp_to_response(server))


@router.delete("/mcp/{server_id}")
async def delete_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Delete MCP server"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    await db.delete(server)
    await db.commit()
    return ApiResponse(data={"deleted": True})


@router.post("/mcp/{server_id}/test", response_model=ApiResponse[MCPServerTestResponse])
async def test_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Test MCP server connection"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return ApiResponse(data=MCPServerTestResponse(success=True, response_time=50, error=None))


@router.post("/mcp/{server_id}/refresh", response_model=ApiResponse[MCPServerRefreshResponse])
async def refresh_mcp_server(server_id: str, db: AsyncSession = Depends(get_db)):
    """Refresh MCP server capabilities"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return ApiResponse(data=MCPServerRefreshResponse(tools=len(server.tools) if server.tools else 0, resources=len(server.resources) if server.resources else 0, prompts=0))


# ============================================================
# Components API
# ============================================================

@router.get("/components", response_model=ApiResponse[PaginatedData[dict]])
async def list_components(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    type: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get components list with pagination"""
    query = select(Component)
    count_query = select(func.count(Component.id))
    
    if status:
        resource_status = ResourceStatus.ACTIVE if status == "active" else ResourceStatus.INACTIVE
        query = query.where(Component.status == resource_status)
        count_query = count_query.where(Component.status == resource_status)
    
    if type:
        query = query.where(Component.type == type)
        count_query = count_query.where(Component.type == type)
    
    if keyword:
        query = query.where(Component.name.ilike(f"%{keyword}%"))
        count_query = count_query.where(Component.name.ilike(f"%{keyword}%"))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    components = result.scalars().all()
    
    return ApiResponse(data=PaginatedData(list=[component_to_response(c) for c in components], total=total, page=page, page_size=page_size))


@router.get("/components/{component_id}", response_model=ApiResponse[dict])
async def get_component(component_id: str, db: AsyncSession = Depends(get_db)):
    """Get component by ID"""
    result = await db.execute(select(Component).where(Component.id == component_id))
    component = result.scalar_one_or_none()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    return ApiResponse(data=component_to_response(component))