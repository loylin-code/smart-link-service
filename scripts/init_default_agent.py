"""
Initialize default Agent for explore center
创建探索中心的默认智能体
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from db.session import async_session_maker
from models.agent import Agent, AgentStatus, AgentType
from models.tenant import Tenant, TenantStatus


async def init_default_agent():
    """Initialize default explore-assistant agent"""
    
    async with async_session_maker() as db:
        # Check if explore-assistant exists
        result = await db.execute(
            select(Agent).where(Agent.code == "explore-assistant")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Agent 'explore-assistant' already exists")
            return
        
        # Get default tenant (or create one)
        result = await db.execute(
            select(Tenant).where(Tenant.slug == "default")
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            # Create default tenant
            tenant = Tenant(
                id="default",
                name="Default Tenant",
                slug="default",
                status=TenantStatus.ACTIVE
            )
            db.add(tenant)
            await db.flush()
            print("Created default tenant")
        
        # Create default agent with flat fields
        agent = Agent(
            id="explore-assistant",
            tenant_id=tenant.id,
            name="探索助手",
            code="explore-assistant",
            type=AgentType.SYSTEM,
            status=AgentStatus.ACTIVE,
            description="探索中心通用智能助手",
            persona="你是一个友好的智能助手，帮助用户解答问题、分析数据、提供建议。",
            welcome_message="你好！我是探索助手，有什么可以帮助你的吗？",
            avatar="🔍",
            llm_config={
                "provider": "bailian",
                "model": "glm-5",
                "temperature": 0.7,
                "maxTokens": 4096,
                "topP": 1.0
            },
            responsibilities=[],
            mcp_servers=[],
            skills=[],
            tools=[],
            documents=[],
            databases=[],
            apis=[],
            search_config={
                "enabled": False,
                "topK": 10,
                "similarityThreshold": 0.7
            },
            tags=["explore", "assistant", "default"],
            version="1.0.0",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(agent)
        await db.commit()
        
        print("Created agent 'explore-assistant' successfully")


if __name__ == "__main__":
    asyncio.run(init_default_agent())