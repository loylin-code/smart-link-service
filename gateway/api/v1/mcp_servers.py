"""
API routes for MCP Server management
Handles CRUD operations and connection management for MCP servers
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.session import get_db
from schemas.mcp import MCPServerCreate, MCPServerUpdate
from models.application import MCPServer, ResourceStatus
from models.tenant import Tenant, TenantStatus
from agent.mcp.client import mcp_manager


router = APIRouter(tags=["MCP Servers"])


# ============================================================
# Helper Functions
# ============================================================

def mcp_server_to_response(server: MCPServer) -> dict:
    """Convert MCPServer model to frontend-expected response format"""
    return {
        "id": server.id,
        "tenant_id": server.tenant_id,
        "name": server.name,
        "description": server.description or "",
        "type": server.type or "stdio",
        "endpoint": server.endpoint or "",
        "config": server.config or {},
        "status": server.status.value if server.status else "active",
        "tools": server.tools or [],
        "resources": server.resources or [],
        "created_at": server.created_at,
        "updated_at": server.updated_at
    }


async def get_mcp_server_or_404(db: AsyncSession, server_id: str) -> MCPServer:
    """Get MCPServer by ID or raise 404"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP Server not found: {server_id}")
    return server


# ============================================================
# MCP Servers API
# ============================================================

@router.get("/", response_model=dict)
async def list_mcp_servers(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List MCP servers with pagination and filters
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20)
    - status: Filter by status (active/inactive)
    - keyword: Search by name or description
    """
    # Get tenant_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    
    query = select(MCPServer)
    count_query = select(func.count(MCPServer.id))
    
    # Filter by tenant
    if tenant_context and tenant_context.is_master:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            query = query.where(MCPServer.tenant_id == tenant.id)
            count_query = count_query.where(MCPServer.tenant_id == tenant.id)
    elif tenant_context and tenant_context.tenant_id:
        query = query.where(MCPServer.tenant_id == tenant_context.tenant_id)
        count_query = count_query.where(MCPServer.tenant_id == tenant_context.tenant_id)
    
    # Filter by status
    if status:
        try:
            resource_status = ResourceStatus(status)
            query = query.where(MCPServer.status == resource_status)
            count_query = count_query.where(MCPServer.status == resource_status)
        except ValueError:
            pass
    
    # Search by keyword
    if keyword:
        keyword_filter = f"%{keyword}%"
        query = query.where(
            (MCPServer.name.ilike(keyword_filter)) | 
            (MCPServer.description.ilike(keyword_filter))
        )
        count_query = count_query.where(
            (MCPServer.name.ilike(keyword_filter)) | 
            (MCPServer.description.ilike(keyword_filter))
        )
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute queries
    result = await db.execute(query)
    servers = result.scalars().all()
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    return {
        "data": {
            "items": [mcp_server_to_response(server) for server in servers],
            "total": total,
            "page": page,
            "pageSize": page_size
        }
    }


@router.post("/", response_model=dict)
async def create_mcp_server(
    request: Request,
    server_data: MCPServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create and connect a new MCP server
    
    Body:
    - name: Server name (required)
    - description: Server description (optional)
    - type: Transport type - 'stdio', 'sse', or 'http' (required)
    - endpoint: Server endpoint URL or command (required)
    - config: Server configuration (optional)
    """
    # Get tenant_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    tenant_id = None
    
    if tenant_context and tenant_context.is_master:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant_id = tenant.id
    elif tenant_context and tenant_context.tenant_id:
        tenant_id = tenant_context.tenant_id
    
    # Create MCP server record
    server = MCPServer(
        tenant_id=tenant_id,
        name=server_data.name,
        description=server_data.description,
        type=server_data.type,
        endpoint=server_data.endpoint,
        config=server_data.config,
        status=ResourceStatus.ACTIVE
    )
    
    db.add(server)
    await db.commit()
    await db.refresh(server)
    
    # Try to connect to the MCP server
    try:
        # Prepare config for mcp_manager
        mcp_config = {
            "type": server.type,
            "endpoint": server.endpoint,
            **(server.config or {})
        }
        
        # Register and connect
        await mcp_manager.register_client(str(server.id), {  # type: ignore
            "type": str(server.type),  # type: ignore
            "endpoint": str(server.endpoint) if server.endpoint else "",  # type: ignore
            **dict(server.config or {})  # type: ignore
        })
        
        # Update server with tools and resources from connected client
        client = mcp_manager.get_client(str(server.id))  # type: ignore
        if client:
            setattr(server, "tools", [tool.model_dump() for tool in client.tools])  # type: ignore
            setattr(server, "resources", [res.model_dump() for res in client.resources])  # type: ignore
            await db.commit()
            await db.refresh(server)
        
    except Exception as e:
        # Connection failed, but server is saved
        # Mark as inactive and save error in config
        setattr(server, "status", ResourceStatus.INACTIVE)  # type: ignore
        setattr(server, "config", {**(dict(server.config) if server.config else {}), "last_error": str(e)})  # type: ignore
        await db.commit()
        await db.refresh(server)
    
    return {"data": mcp_server_to_response(server)}


@router.get("/{server_id}", response_model=dict)
async def get_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single MCP server by ID
    """
    server = await get_mcp_server_or_404(db, server_id)
    return {"data": mcp_server_to_response(server)}


@router.put("/{server_id}", response_model=dict)
async def update_mcp_server(
    server_id: str,
    server_data: MCPServerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing MCP server
    
    Body (all fields optional):
    - name: Server name
    - description: Server description
    - type: Transport type
    - endpoint: Server endpoint
    - config: Server configuration
    - status: Server status
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    # Update fields
    update_data = server_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(server, field, value)
    
    # If endpoint or type changed, reconnect
    if "endpoint" in update_data or "type" in update_data:
        # Disconnect if currently connected
        if mcp_manager.get_client(str(server.id)):  # type: ignore
            await mcp_manager.unregister_client(str(server.id))  # type: ignore
        
        # Try to reconnect if server is active
        if server.status == ResourceStatus.ACTIVE:
            try:
                await mcp_manager.register_client(str(server.id), {  # type: ignore
                    "type": str(server.type),  # type: ignore
                    "endpoint": str(server.endpoint) if server.endpoint else "",  # type: ignore
                    **dict(server.config or {})  # type: ignore
                })
                
                # Update tools and resources
                client = mcp_manager.get_client(str(server.id))  # type: ignore
                if client:
                    setattr(server, "tools", [tool.model_dump() for tool in client.tools])  # type: ignore
                    setattr(server, "resources", [res.model_dump() for res in client.resources])  # type: ignore
            except Exception as e:
                setattr(server, "status", ResourceStatus.INACTIVE)  # type: ignore
                setattr(server, "config", {**(dict(server.config) if server.config else {}), "last_error": str(e)})  # type: ignore
    
    await db.commit()
    await db.refresh(server)
    
    return {"data": mcp_server_to_response(server)}


@router.delete("/{server_id}", response_model=dict)
async def delete_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an MCP server (disconnects first if connected)
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    # Disconnect if connected
    if mcp_manager.get_client(str(server_id)):  # type: ignore
        await mcp_manager.unregister_client(str(server_id))  # type: ignore
    
    # Delete from database
    await db.delete(server)
    await db.commit()
    
    return {"data": {"message": "MCP server deleted successfully"}}


@router.post("/{server_id}/connect", response_model=dict)
async def connect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Test connection to an MCP server
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    # Disconnect if already connected
    if mcp_manager.get_client(str(server_id)):  # type: ignore
        await mcp_manager.unregister_client(str(server_id))  # type: ignore
    
    try:
        # Prepare config
        await mcp_manager.register_client(str(server_id), {  # type: ignore
            "type": str(server.type),  # type: ignore
            "endpoint": str(server.endpoint) if server.endpoint else "",  # type: ignore
            **dict(server.config or {})  # type: ignore
        })
        
        # Update server with tools and resources
        client = mcp_manager.get_client(str(server_id))  # type: ignore
        if client:
            setattr(server, "tools", [tool.model_dump() for tool in client.tools])  # type: ignore
            setattr(server, "resources", [res.model_dump() for res in client.resources])  # type: ignore
            setattr(server, "status", ResourceStatus.ACTIVE)  # type: ignore
        
        await db.commit()
        await db.refresh(server)
        
        return {"data": {"connected": True, "tools": len(server.tools) if server.tools else 0}}  # type: ignore
        
    except Exception as e:
        setattr(server, "status", ResourceStatus.INACTIVE)  # type: ignore
        setattr(server, "config", {**(dict(server.config) if server.config else {}), "last_error": str(e)})  # type: ignore
        await db.commit()
        
        return {"data": {"connected": False, "error": str(e)}}


@router.post("/{server_id}/disconnect", response_model=dict)
async def disconnect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect from an MCP server
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    # Disconnect if connected
    if mcp_manager.get_client(str(server_id)):  # type: ignore
        await mcp_manager.unregister_client(str(server_id))  # type: ignore
    
    # Update status
    setattr(server, "status", ResourceStatus.INACTIVE)  # type: ignore
    
    await db.commit()
    await db.refresh(server)
    
    return {"data": {"message": "MCP server disconnected"}}


@router.get("/{server_id}/tools")
async def get_mcp_server_tools(
    server_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List tools available from MCP Server
    
    Args:
        server_id: MCP Server ID
        db: Database session
        
    Returns:
        Tools list with total count
        
    Raises:
        HTTPException 400 if server is not active
        HTTPException 404 if server not found
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    if server.status != ResourceStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"MCP Server {server_id} is not active"
        )
    
    tools = server.tools or []
    
    return {
        "data": {
            "tools": tools,
            "total": len(tools)
        }
    }
