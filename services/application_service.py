"""
Application service layer
"""
from typing import Tuple, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from models.application import Application, AppStatus, AppType
from schemas.common import ApplicationCreate, ApplicationUpdate
from core.exceptions import NotFoundError, ValidationError


class ApplicationService:
    """Service for application management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_applications(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[AppStatus] = None,
        type: Optional[AppType] = None,
        keyword: Optional[str] = None
    ) -> Tuple[List[Application], int]:
        """
        List applications with pagination and filters
        
        Returns:
            Tuple of (applications list, total count)
        """
        # Build query
        query = select(Application)
        
        # Apply filters
        if status:
            query = query.where(Application.status == status)
        
        if type:
            query = query.where(Application.type == type)
        
        if keyword:
            keyword_filter = or_(
                Application.name.ilike(f"%{keyword}%"),
                Application.description.ilike(f"%{keyword}%")
            )
            query = query.where(keyword_filter)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        query = query.order_by(Application.created_at.desc())
        
        # Execute query
        result = await self.db.execute(query)
        applications = result.scalars().all()
        
        return applications, total
    
    async def get_application(self, app_id: str) -> Optional[Application]:
        """Get application by ID"""
        query = select(Application).where(Application.id == app_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_application(self, app_data: ApplicationCreate) -> Application:
        """Create a new application"""
        # Generate ID
        import uuid
        app_id = f"app_{uuid.uuid4().hex[:12]}"
        
        # Create application
        application = Application(
            id=app_id,
            name=app_data.name,
            description=app_data.description,
            icon=app_data.icon,
            type=app_data.type,
            status=AppStatus.DRAFT,
            version="0.1.0",
            schema=app_data.schema or {}
        )
        
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        
        return application
    
    async def update_application(
        self,
        app_id: str,
        app_data: ApplicationUpdate
    ) -> Optional[Application]:
        """Update application"""
        application = await self.get_application(app_id)
        
        if not application:
            return None
        
        # Update fields
        update_data = app_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(application, field, value)
        
        application.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(application)
        
        return application
    
    async def delete_application(self, app_id: str) -> bool:
        """Delete application"""
        application = await self.get_application(app_id)
        
        if not application:
            return False
        
        await self.db.delete(application)
        await self.db.commit()
        
        return True
    
    async def publish_application(self, app_id: str) -> Optional[Application]:
        """Publish application"""
        application = await self.get_application(app_id)
        
        if not application:
            return None
        
        application.status = AppStatus.PUBLISHED
        application.published_at = datetime.utcnow()
        application.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(application)
        
        return application
    
    async def run_application(
        self,
        app_id: str,
        input_data: dict
    ) -> dict:
        """Run application with input data"""
        from agent.core.orchestrator import AgentOrchestrator
        
        application = await self.get_application(app_id)
        
        if not application:
            raise NotFoundError("Application", app_id)
        
        if application.status != AppStatus.PUBLISHED:
            raise ValidationError("Application must be published before running")
        
        # Execute agent
        orchestrator = AgentOrchestrator(config={})
        result = await orchestrator.execute(
            app_id=app_id,
            input_data=input_data
        )
        
        return result