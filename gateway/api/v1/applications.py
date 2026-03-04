"""
API routes for application management
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.common import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationListResponse,
    ResponseBase
)
from services.application_service import ApplicationService
from models.application import AppStatus, AppType

router = APIRouter()


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    page: int = 1,
    page_size: int = 20,
    status: Optional[AppStatus] = None,
    type: Optional[AppType] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List applications with pagination and filters
    
    - **page**: Page number (default: 1)
    - **page_size**: Page size (default: 20, max: 100)
    - **status**: Filter by status
    - **type**: Filter by type
    - **keyword**: Search keyword
    """
    service = ApplicationService(db)
    
    applications, total = await service.list_applications(
        page=page,
        page_size=page_size,
        status=status,
        type=type,
        keyword=keyword
    )
    
    return ApplicationListResponse(
        code=200,
        message="success",
        total=total,
        page=page,
        page_size=page_size,
        data=[ApplicationResponse.from_orm(app) for app in applications]
    )


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    app_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new application
    
    - **name**: Application name (required)
    - **description**: Application description
    - **icon**: Application icon
    - **type**: Application type (workflow/chart/form/dashboard/custom)
    - **schema**: Application flow schema
    """
    service = ApplicationService(db)
    application = await service.create_application(app_data)
    
    return ApplicationResponse.from_orm(application)


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get application by ID
    """
    service = ApplicationService(db)
    application = await service.get_application(app_id)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    return ApplicationResponse.from_orm(application)


@router.put("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: str,
    app_data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update application
    
    All fields are optional - only provided fields will be updated
    """
    service = ApplicationService(db)
    application = await service.update_application(app_id, app_data)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    return ApplicationResponse.from_orm(application)


@router.delete("/{app_id}", response_model=ResponseBase)
async def delete_application(
    app_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete application
    """
    service = ApplicationService(db)
    success = await service.delete_application(app_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    return ResponseBase(code=200, message="Application deleted successfully")


@router.post("/{app_id}/publish", response_model=ApplicationResponse)
async def publish_application(
    app_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Publish application
    
    Changes status to 'published' and sets published_at timestamp
    """
    service = ApplicationService(db)
    application = await service.publish_application(app_id)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {app_id} not found"
        )
    
    return ApplicationResponse.from_orm(application)


@router.post("/{app_id}/run", response_model=dict)
async def run_application(
    app_id: str,
    input_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Run application
    
    Execute the application with provided input data
    """
    service = ApplicationService(db)
    result = await service.run_application(app_id, input_data)
    
    return result