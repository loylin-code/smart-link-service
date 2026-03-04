"""
Resource service layer (Skills, MCP, Components)
"""
from typing import Tuple, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.application import Skill, MCPServer, Component, ResourceStatus
from schemas.common import SkillCreate, SkillUpdate, MCPServerCreate, MCPServerUpdate


class ResourceService:
    """Service for resource management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============================================================
    # Skills
    # ============================================================
    
    async def list_skills(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[ResourceStatus] = None
    ) -> Tuple[List[Skill], int]:
        """List skills with pagination"""
        query = select(Skill)
        
        if status:
            query = query.where(Skill.status == status)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()
        
        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        query = query.order_by(Skill.created_at.desc())
        
        result = await self.db.execute(query)
        skills = result.scalars().all()
        
        return skills, total
    
    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get skill by ID"""
        query = select(Skill).where(Skill.id == skill_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_skill(self, skill_data: SkillCreate) -> Skill:
        """Create a new skill"""
        import uuid
        skill_id = f"skill_{uuid.uuid4().hex[:12]}"
        
        skill = Skill(
            id=skill_id,
            name=skill_data.name,
            description=skill_data.description,
            type=skill_data.type,
            status=ResourceStatus.ACTIVE,
            config=skill_data.config
        )
        
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)
        
        return skill
    
    async def update_skill(
        self,
        skill_id: str,
        skill_data: SkillUpdate
    ) -> Optional[Skill]:
        """Update skill"""
        skill = await self.get_skill(skill_id)
        
        if not skill:
            return None
        
        update_data = skill_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(skill, field, value)
        
        skill.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(skill)
        
        return skill
    
    async def delete_skill(self, skill_id: str) -> bool:
        """Delete skill"""
        skill = await self.get_skill(skill_id)
        
        if not skill:
            return False
        
        await self.db.delete(skill)
        await self.db.commit()
        
        return True
    
    # ============================================================
    # MCP Servers
    # ============================================================
    
    async def list_mcp_servers(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[ResourceStatus] = None
    ) -> Tuple[List[MCPServer], int]:
        """List MCP servers with pagination"""
        query = select(MCPServer)
        
        if status:
            query = query.where(MCPServer.status == status)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()
        
        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        query = query.order_by(MCPServer.created_at.desc())
        
        result = await self.db.execute(query)
        servers = result.scalars().all()
        
        return servers, total
    
    async def get_mcp_server(self, server_id: str) -> Optional[MCPServer]:
        """Get MCP server by ID"""
        query = select(MCPServer).where(MCPServer.id == server_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_mcp_server(self, server_data: MCPServerCreate) -> MCPServer:
        """Create a new MCP server"""
        import uuid
        server_id = f"mcp_{uuid.uuid4().hex[:12]}"
        
        server = MCPServer(
            id=server_id,
            name=server_data.name,
            description=server_data.description,
            type=server_data.type,
            endpoint=server_data.endpoint,
            status=ResourceStatus.ACTIVE,
            config=server_data.config
        )
        
        self.db.add(server)
        await self.db.commit()
        await self.db.refresh(server)
        
        return server
    
    async def update_mcp_server(
        self,
        server_id: str,
        server_data: MCPServerUpdate
    ) -> Optional[MCPServer]:
        """Update MCP server"""
        server = await self.get_mcp_server(server_id)
        
        if not server:
            return None
        
        update_data = server_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(server, field, value)
        
        server.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(server)
        
        return server
    
    async def delete_mcp_server(self, server_id: str) -> bool:
        """Delete MCP server"""
        server = await self.get_mcp_server(server_id)
        
        if not server:
            return False
        
        await self.db.delete(server)
        await self.db.commit()
        
        return True
    
    # ============================================================
    # Components
    # ============================================================
    
    async def list_components(
        self,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Component], int]:
        """List components with pagination"""
        query = select(Component)
        
        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()
        
        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        query = query.order_by(Component.created_at.desc())
        
        result = await self.db.execute(query)
        components = result.scalars().all()
        
        return components, total