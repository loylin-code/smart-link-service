"""
API routes for application management
Aligned with frontend service expectations
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.time_utils import now_utc8
from db.session import get_db
from schemas import (
    ApiResponse, PaginatedData,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse, RunApplicationRequest
)
from models import Application, AppStatus, AppType, Tenant, TenantStatus
from models.application import ResourceStatus
from agent.core.orchestrator import AgentOrchestrator


router = APIRouter(tags=["Applications"])


# ============================================================
# Helper Functions
# ============================================================

def app_to_response(app: Application) -> dict:
    """Convert Application model to frontend-expected response format"""
    return {
        "id": app.id,
        "name": app.name,
        "description": app.description or "",
        "icon": app.icon or "app",
        "type": app.type.value if app.type else "custom",
        "status": app.status.value if app.status else "draft",
        "version": app.version or "0.1.0",
        "tags": [],
        "schema": app.schema or {},
        "created_at": app.created_at,
        "updated_at": app.updated_at,
        "published_at": app.published_at,
        "is_enabled": app.status == AppStatus.PUBLISHED
    }


# ============================================================
# Applications API
# ============================================================

@router.get("/", response_model=ApiResponse[PaginatedData[dict]])
async def list_applications(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: Optional[str] = None,
    type: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List applications with pagination and filters
    
    Frontend expects:
    - GET /applications/?page=1&page_size=20&status=draft&type=workflow&keyword=search
    """
    # Get tenant_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    
    query = select(Application)
    count_query = select(func.count(Application.id))
    
    # For master key, get first active tenant
    if tenant_context and tenant_context.is_master:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            query = query.where(Application.tenant_id == tenant.id)
            count_query = count_query.where(Application.tenant_id == tenant.id)
    elif tenant_context and tenant_context.tenant_id:
        query = query.where(Application.tenant_id == tenant_context.tenant_id)
        count_query = count_query.where(Application.tenant_id == tenant_context.tenant_id)
    
    if status:
        try:
            app_status = AppStatus(status)
            query = query.where(Application.status == app_status)
            count_query = count_query.where(Application.status == app_status)
        except ValueError:
            pass
    
    if type:
        try:
            app_type = AppType(type)
            query = query.where(Application.type == app_type)
            count_query = count_query.where(Application.type == app_type)
        except ValueError:
            pass
    
    if keyword:
        query = query.where(Application.name.ilike(f"%{keyword}%"))
        count_query = count_query.where(Application.name.ilike(f"%{keyword}%"))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    applications = result.scalars().all()
    
    return ApiResponse(
        data=PaginatedData(
            list=[app_to_response(app) for app in applications],
            total=total,
            page=page,
            page_size=page_size
        )
    )


@router.post("/", response_model=ApiResponse[dict])
async def create_application(
    data: ApplicationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Create a new application"""
    import uuid
    
    # Get tenant_id from request context
    tenant_context = getattr(request.state, "tenant_context", None)
    
    # For master key, get first active tenant
    if tenant_context and tenant_context.is_master:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=400, detail="No active tenant found")
        tenant_id = tenant.id
    elif tenant_context and tenant_context.tenant_id:
        tenant_id = tenant_context.tenant_id
    else:
        raise HTTPException(status_code=400, detail="Tenant ID is required")
    
    application = Application(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=data.name,
        description=data.description or "",
        icon=data.icon or "app",
        type=data.type or AppType.CUSTOM,
        status=AppStatus.DRAFT,
        schema=data.schema or {},
        tags=data.tags or []
    )
    
    db.add(application)
    await db.commit()
    await db.refresh(application)
    
    return ApiResponse(data=app_to_response(application))


@router.get("/{app_id}", response_model=ApiResponse[dict])
async def get_application(
    app_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get application by ID"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    return ApiResponse(data=app_to_response(application))


@router.put("/{app_id}", response_model=ApiResponse[dict])
async def update_application(
    app_id: str,
    data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update application"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Convert string enums to proper types
    if "status" in update_data and isinstance(update_data["status"], str):
        update_data["status"] = AppStatus(update_data["status"])
    if "type" in update_data and isinstance(update_data["type"], str):
        update_data["type"] = AppType(update_data["type"])
    
    for key, value in update_data.items():
        setattr(application, key, value)
    
    await db.commit()
    await db.refresh(application)
    
    return ApiResponse(data=app_to_response(application))


@router.delete("/{app_id}")
async def delete_application(
    app_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete application"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    await db.delete(application)
    await db.commit()
    
    return ApiResponse(data={"deleted": True})


@router.post("/{app_id}/publish", response_model=ApiResponse[dict])
async def publish_application(
    app_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Publish application"""
    from datetime import datetime
    
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    application.status = AppStatus.PUBLISHED
    application.published_at = now_utc8()
    
    await db.commit()
    await db.refresh(application)
    
    return ApiResponse(data=app_to_response(application))


@router.post("/{app_id}/run")
async def run_application(
    app_id: str,
    data: RunApplicationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Run application"""
    from datetime import datetime
    import uuid
    
    # Get application
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if application.status != AppStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Application must be published before running")
    
    # Create conversation for this run
    from models import Conversation
    conversation = Conversation(
        id=str(uuid.uuid4()),
        tenant_id=application.tenant_id,
        title=f"Run: {application.name}",
        app_id=app_id
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    # Execute agent
    try:
        orchestrator = AgentOrchestrator()
        result = await orchestrator.execute(
            app_id=app_id,
            input_data=data.input_data or {},
            conversation_id=conversation.id
        )
        
        return ApiResponse(data={
            "conversation_id": conversation.id,
            "result": result,
            "status": "completed"
        })
    except Exception as e:
        return ApiResponse(
            code=500,
            message=str(e),
            data={
                "conversation_id": conversation.id,
                "result": None,
                "status": "error",
                "error": str(e)
            }
        )