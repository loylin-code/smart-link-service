"""
API routes for Plugin Marketplace
Handles plugin publishing, discovery, and installation
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from schemas.plugin import (
    PluginCreate,
    PluginUpdate,
    PluginResponse,
    PluginInstallRequest,
    PluginInstallationResponse,
    PluginListResponse
)
from models.plugin import Plugin, PluginInstallation, PluginStatus


router = APIRouter(tags=["Plugins"])


def plugin_to_response(plugin: Plugin) -> PluginResponse:
    """Convert Plugin model to response"""
    return PluginResponse(
        id=plugin.id,
        tenant_id=plugin.tenant_id,
        name=plugin.name,
        description=plugin.description,
        version=plugin.version,
        author=plugin.author,
        license=plugin.license,
        tags=plugin.tags or [],
        icon=plugin.icon,
        status=plugin.status.value,
        install_count=plugin.install_count or 0,
        created_at=plugin.created_at,
        updated_at=plugin.updated_at
    )


async def get_plugin_or_404(db: AsyncSession, plugin_id: str) -> Plugin:
    """Get Plugin by ID or raise 404"""
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")
    return plugin


@router.get("/")
async def list_plugins(
    search: Optional[str] = Query(None, description="Search by name"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List published plugins with optional search and filtering"""
    query = select(Plugin).where(Plugin.status == PluginStatus.PUBLISHED)
    
    if search:
        query = query.where(Plugin.name.ilike(f"%{search}%"))
    
    if tag:
        query = query.where(Plugin.tags.contains([tag]))
    
    query = query.order_by(Plugin.install_count.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    plugins = result.scalars().all()
    
    # Get total count
    count_query = select(Plugin).where(Plugin.status == PluginStatus.PUBLISHED)
    if search:
        count_query = count_query.where(Plugin.name.ilike(f"%{search}%"))
    if tag:
        count_query = count_query.where(Plugin.tags.contains([tag]))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    return {
        "data": [plugin_to_response(p) for p in plugins],
        "total": total
    }


@router.post("/")
async def publish_plugin(
    request: PluginCreate,
    tenant_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Publish a new plugin to marketplace"""
    # Check for duplicate name
    existing = await db.execute(
        select(Plugin).where(Plugin.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Plugin with name '{request.name}' already exists"
        )
    
    plugin = Plugin(
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        version=request.version,
        author=request.author,
        license=request.license,
        tags=request.tags,
        icon=request.icon,
        package_name=request.package_name,
        package_version=request.package_version,
        entry_point=request.entry_point,
        status=PluginStatus.PUBLISHED
    )
    
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)
    
    return {"data": plugin_to_response(plugin)}


@router.get("/{plugin_id}")
async def get_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get plugin details by ID"""
    plugin = await get_plugin_or_404(db, plugin_id)
    return {"data": plugin_to_response(plugin)}


@router.put("/{plugin_id}")
async def update_plugin(
    plugin_id: str,
    request: PluginUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update plugin metadata"""
    plugin = await get_plugin_or_404(db, plugin_id)
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            plugin.status = PluginStatus(value)
        else:
            setattr(plugin, field, value)
    
    await db.commit()
    await db.refresh(plugin)
    
    return {"data": plugin_to_response(plugin)}


@router.delete("/{plugin_id}")
async def unpublish_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Unpublish plugin from marketplace"""
    plugin = await get_plugin_or_404(db, plugin_id)
    plugin.status = PluginStatus.UNPUBLISHED
    await db.commit()
    
    return {"data": {"message": f"Plugin {plugin_id} unpublished"}}


@router.post("/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    request: PluginInstallRequest,
    tenant_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Install plugin to tenant"""
    plugin = await get_plugin_or_404(db, plugin_id)
    
    if plugin.status != PluginStatus.PUBLISHED:
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_id} is not available for installation"
        )
    
    # Check if already installed
    existing = await db.execute(
        select(PluginInstallation).where(
            PluginInstallation.tenant_id == tenant_id,
            PluginInstallation.plugin_id == plugin_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Plugin {plugin_id} is already installed for this tenant"
        )
    
    installation = PluginInstallation(
        tenant_id=tenant_id,
        plugin_id=plugin_id,
        settings=request.settings,
        enabled=request.enabled
    )
    
    db.add(installation)
    plugin.install_count += 1
    
    await db.commit()
    await db.refresh(installation)
    
    return {
        "data": PluginInstallationResponse(
            id=installation.id,
            tenant_id=installation.tenant_id,
            plugin_id=installation.plugin_id,
            plugin_name=plugin.name,
            enabled=installation.enabled,
            settings=installation.settings,
            installed_at=installation.installed_at
        )
    }


@router.delete("/{plugin_id}/uninstall")
async def uninstall_plugin(
    plugin_id: str,
    tenant_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Uninstall plugin from tenant"""
    # Find installation
    result = await db.execute(
        select(PluginInstallation).where(
            PluginInstallation.tenant_id == tenant_id,
            PluginInstallation.plugin_id == plugin_id
        )
    )
    installation = result.scalar_one_or_none()
    
    if not installation:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin {plugin_id} is not installed for this tenant"
        )
    
    # Decrease install count
    plugin = await get_plugin_or_404(db, plugin_id)
    plugin.install_count = max(0, plugin.install_count - 1)
    
    await db.delete(installation)
    await db.commit()
    
    return {"data": {"message": f"Plugin {plugin_id} uninstalled"}}


@router.get("/installed")
async def list_installed_plugins(
    tenant_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List plugins installed for a tenant"""
    result = await db.execute(
        select(PluginInstallation).where(
            PluginInstallation.tenant_id == tenant_id
        )
    )
    installations = result.scalars().all()
    
    # Get plugin details for each installation
    response_data = []
    for inst in installations:
        plugin = await get_plugin_or_404(db, inst.plugin_id)
        response_data.append(
            PluginInstallationResponse(
                id=inst.id,
                tenant_id=inst.tenant_id,
                plugin_id=inst.plugin_id,
                plugin_name=plugin.name,
                enabled=inst.enabled,
                settings=inst.settings,
                installed_at=inst.installed_at
            )
        )
    
    return {"data": response_data, "total": len(response_data)}