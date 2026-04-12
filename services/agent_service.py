"""
Agent Service - Business logic for Agent management
"""
from typing import Optional, List
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import update

from models.agent import Agent, AgentRuntimeStatus, AgentStatus, AgentType
from schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    agent_to_response
)
from schemas.common import PaginatedData


class AgentService:
    """Agent service for CRUD operations"""
    
    @staticmethod
    async def create_agent(
        db: AsyncSession,
        tenant_id: str,
        data: AgentCreate,
        user_id: Optional[str] = None
    ) -> Agent:
        """
        Create a new agent
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            data: Agent creation data
            user_id: Creator user ID
            
        Returns:
            Created Agent instance
        """
        agent = Agent(
            tenant_id=tenant_id,
            name=data.name,
            code=data.code,
            description=data.description or "",
            avatar=data.avatar,
            persona=data.persona or "",
            welcome_message=data.welcome_message or "",
            tags=data.tags or [],
            category=data.category,
            type=AgentType.CUSTOM,
            status=AgentStatus.DRAFT,
            creator=user_id,
            # Default capabilities
            mcp_servers=[],
            skills=[],
            tools=[],
            llm_config={
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
                "maxTokens": 4096,
                "topP": 1
            },
            # Default knowledge
            documents=[],
            databases=[],
            apis=[],
            search_config={
                "enabled": False,
                "topK": 10,
                "similarityThreshold": 0.7,
                "rerankEnabled": False
            }
        )
        
        db.add(agent)
        await db.flush()
        await db.refresh(agent)
        
        return agent
    
    @staticmethod
    async def get_agent_by_id(db: AsyncSession, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        result = await db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_agent_by_code(
        db: AsyncSession,
        tenant_id: str,
        code: str
    ) -> Optional[Agent]:
        """Get agent by code within tenant"""
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.code == code
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_agents(
        db: AsyncSession,
        tenant_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[AgentStatus] = None,
        type: Optional[AgentType] = None,
        keyword: Optional[str] = None,
        category: Optional[str] = None
    ) -> PaginatedData:
        """
        List agents with pagination and filters
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            page: Page number
            page_size: Page size
            status: Filter by status
            type: Filter by type
            keyword: Search keyword
            category: Filter by category
            
        Returns:
            PaginatedData with Agent list
        """
        # Build query
        query = select(Agent).where(Agent.tenant_id == tenant_id)
        count_query = select(func.count(Agent.id)).where(Agent.tenant_id == tenant_id)
        
        # Apply filters
        if status:
            query = query.where(Agent.status == status)
            count_query = count_query.where(Agent.status == status)
        
        if type:
            query = query.where(Agent.type == type)
            count_query = count_query.where(Agent.type == type)
        
        if category:
            query = query.where(Agent.category == category)
            count_query = count_query.where(Agent.category == category)
        
        if keyword:
            search_pattern = f"%{keyword}%"
            query = query.where(
                or_(
                    Agent.name.ilike(search_pattern),
                    Agent.description.ilike(search_pattern)
                )
            )
            count_query = count_query.where(
                or_(
                    Agent.name.ilike(search_pattern),
                    Agent.description.ilike(search_pattern)
                )
            )
        
        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(Agent.updated_at.desc()).offset(offset).limit(page_size)
        
        # Execute query
        result = await db.execute(query)
        agents = result.scalars().all()
        
        return PaginatedData(
            list=agents,
            total=total,
            page=page,
            page_size=page_size
        )
    
    @staticmethod
    async def update_agent(
        db: AsyncSession,
        agent_id: str,
        data: AgentUpdate
    ) -> Optional[Agent]:
        """
        Update agent
        
        Args:
            db: Database session
            agent_id: Agent ID
            data: Update data
            
        Returns:
            Updated Agent or None
        """
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return None
        
        # Update simple fields
        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.avatar is not None:
            agent.avatar = data.avatar
        if data.persona is not None:
            agent.persona = data.persona
        if data.welcome_message is not None:
            agent.welcome_message = data.welcome_message
        if data.tags is not None:
            agent.tags = data.tags
        if data.status is not None:
            agent.status = data.status
        
        # Update nested objects
        if data.identity is not None:
            agent.name = data.identity.name
            agent.code = data.identity.code
            agent.avatar = data.identity.avatar
            agent.description = data.identity.description
            agent.persona = data.identity.persona
            agent.welcome_message = data.identity.welcome_message
            agent.responsibilities = [r.model_dump() for r in data.identity.responsibilities]
        
        if data.capabilities is not None:
            agent.mcp_servers = [b.model_dump(by_alias=True) for b in data.capabilities.mcp_servers]
            agent.skills = [b.model_dump(by_alias=True) for b in data.capabilities.skills]
            agent.tools = [b.model_dump(by_alias=True) for b in data.capabilities.tools]
            agent.llm_config = data.capabilities.llm.model_dump(by_alias=True)
        
        if data.knowledge is not None:
            agent.documents = [d.model_dump() for d in data.knowledge.documents]
            agent.databases = [d.model_dump() for d in data.knowledge.databases]
            agent.apis = [a.model_dump() for a in data.knowledge.apis]
            agent.search_config = data.knowledge.search_config.model_dump(by_alias=True)
        
        if data.page_schema is not None:
            agent.page_schema = data.page_schema
        
        await db.flush()
        await db.refresh(agent)
        
        return agent
    
    @staticmethod
    async def delete_agent(db: AsyncSession, agent_id: str) -> bool:
        """Delete agent"""
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return False
        
        await db.delete(agent)
        await db.flush()
        return True
    
    @staticmethod
    async def duplicate_agent(
        db: AsyncSession,
        agent_id: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Agent]:
        """
        Duplicate an agent
        
        Args:
            db: Database session
            agent_id: Source agent ID
            tenant_id: Target tenant ID
            user_id: Creator user ID
            
        Returns:
            New Agent or None
        """
        original = await AgentService.get_agent_by_id(db, agent_id)
        if not original:
            return None
        
        # Create copy
        new_agent = Agent(
            tenant_id=tenant_id,
            name=f"{original.name} (副本)",
            code=f"{original.code}_copy_{int(datetime.utcnow().timestamp())}",
            description=original.description,
            avatar=original.avatar,
            persona=original.persona,
            welcome_message=original.welcome_message,
            responsibilities=original.responsibilities,
            tags=original.tags,
            category=original.category,
            type=AgentType.CUSTOM,
            status=AgentStatus.DRAFT,
            creator=user_id,
            mcp_servers=original.mcp_servers,
            skills=original.skills,
            tools=original.tools,
            llm_config=original.llm_config,
            documents=original.documents,
            databases=original.databases,
            apis=original.apis,
            search_config=original.search_config,
            page_schema=original.page_schema
        )
        
        db.add(new_agent)
        await db.flush()
        await db.refresh(new_agent)
        
        return new_agent
    
    @staticmethod
    async def activate_agent(db: AsyncSession, agent_id: str) -> Optional[Agent]:
        """Activate agent (change status to ACTIVE)"""
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return None
        
        agent.status = AgentStatus.ACTIVE
        await db.flush()
        await db.refresh(agent)
        return agent
    
    @staticmethod
    async def pause_agent(db: AsyncSession, agent_id: str) -> Optional[Agent]:
        """Pause agent (change status to PAUSED)"""
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return None
        
        agent.status = AgentStatus.PAUSED
        await db.flush()
        await db.refresh(agent)
        return agent
    
    @staticmethod
    async def update_capabilities(
        db: AsyncSession,
        agent_id: str,
        capabilities: dict
    ) -> Optional[Agent]:
        """Update agent capabilities"""
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return None
        
        if 'mcpServers' in capabilities:
            agent.mcp_servers = capabilities['mcpServers']
        if 'skills' in capabilities:
            agent.skills = capabilities['skills']
        if 'tools' in capabilities:
            agent.tools = capabilities['tools']
        if 'llm' in capabilities:
            agent.llm_config = capabilities['llm']
        
        await db.flush()
        await db.refresh(agent)
        return agent
    
    @staticmethod
    async def update_knowledge(
        db: AsyncSession,
        agent_id: str,
        knowledge: dict
    ) -> Optional[Agent]:
        """Update agent knowledge configuration"""
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return None
        
        if 'documents' in knowledge:
            agent.documents = knowledge['documents']
        if 'databases' in knowledge:
            agent.databases = knowledge['databases']
        if 'apis' in knowledge:
            agent.apis = knowledge['apis']
        if 'searchConfig' in knowledge:
            agent.search_config = knowledge['searchConfig']
        
        await db.flush()
        await db.refresh(agent)
        return agent


# Import datetime for duplicate_agent
from datetime import datetime