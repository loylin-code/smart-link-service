"""
Database initialization script
Creates all tables and seeds initial data
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from passlib.context import CryptContext

from db.session import init_db, close_db, async_session_maker
from core.config import settings
from core.security import generate_api_key, get_password_hash

# Import all models to register them with Base.metadata
from models import (
    # Tenant models
    Tenant, User, TenantSettings, TenantStatus, BillingPlan, UserRole,
    # Application models
    Application, Conversation, Message, Resource, ResourceVersion,
    Skill, MCPServer, Component, APIKey, AuditLog,
    AppStatus, AppType, ResourceStatus,
    # Workflow models
    Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution, NodeExecution,
    WorkflowStatus, NodeType, ExecutionStatus
)


async def seed_initial_data():
    """
    Seed initial data for development/testing
    Creates:
    - Default tenant
    - Admin user
    - Sample application
    - API keys
    """
    print("Seeding initial data...")
    
    async with async_session_maker() as db:
        from sqlalchemy import select
        
        # Check if default tenant exists
        result = await db.execute(
            select(Tenant).where(Tenant.slug == "default")
        )
        if result.scalar_one_or_none():
            print("[SKIP] Default tenant already exists")
            return
        
        # Create default tenant
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name="Default Tenant",
            slug="default",
            status=TenantStatus.ACTIVE,
            billing_plan=BillingPlan.ENTERPRISE,
            max_sessions=1000,
            max_agents=50,
            max_users=100,
            monthly_token_limit=10_000_000,
            monthly_request_limit=1_000_000,
            settings={
                "default_llm_provider": settings.DEFAULT_LLM_PROVIDER,
                "default_llm_model": settings.DEFAULT_LLM_MODEL,
            }
        )
        db.add(tenant)
        
        # Create admin user
        admin_user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email="admin@smartlink.local",
            password_hash=get_password_hash("admin123"),  # Change in production!
            full_name="Admin User",
            role=UserRole.OWNER,
            is_active=True,
            is_verified=True,
            preferences={
                "theme": "light",
                "language": "en"
            }
        )
        db.add(admin_user)
        
        # Create tenant settings
        tenant_settings = TenantSettings(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            default_llm_provider=settings.DEFAULT_LLM_PROVIDER,
            default_llm_model=settings.DEFAULT_LLM_MODEL,
            enable_web_search=True,
            enable_file_upload=True,
            enable_mcp=True,
        )
        db.add(tenant_settings)
        
        # Create sample application
        sample_app = Application(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            name="Smart Assistant",
            description="A general-purpose AI assistant",
            type=AppType.WORKFLOW,
            status=AppStatus.PUBLISHED,
            created_by=admin_user.id,
            schema={
                "nodes": [
                    {"id": "start", "type": "start", "config": {}},
                    {"id": "llm_1", "type": "llm", "config": {"model": "gpt-4o-mini"}},
                    {"id": "end", "type": "end", "config": {}}
                ],
                "edges": [
                    {"source": "start", "target": "llm_1"},
                    {"source": "llm_1", "target": "end"}
                ]
            },
            skills=["web_search"],
        )
        db.add(sample_app)
        
        # Create API keys
        # Master API key for admin
        master_key = generate_api_key()
        api_key = APIKey(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            user_id=admin_user.id,
            key_hash=master_key,  # In production, this should be hashed
            key_prefix=master_key[:8],
            name="Master API Key",
            description="Full access API key for development",
            is_active=True,
            scopes=["*"],  # All scopes
            rate_limit=1000,
            expires_at=datetime.utcnow() + timedelta(days=365)
        )
        db.add(api_key)
        
        # Create builtin skills
        builtin_skills = [
            Skill(
                id=str(uuid.uuid4()),
                tenant_id=None,  # Builtin skills have no tenant
                name="web_search",
                description="Search the web for information",
                type="builtin",
                status=ResourceStatus.ACTIVE,
                config={"provider": "duckduckgo"},
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {"type": "integer", "default": 5, "description": "Number of results"}
                    },
                    "required": ["query"]
                }
            ),
            Skill(
                id=str(uuid.uuid4()),
                tenant_id=None,
                name="data_analysis",
                description="Analyze data and generate insights",
                type="builtin",
                status=ResourceStatus.ACTIVE,
                config={},
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to analyze"},
                        "analysis_type": {"type": "string", "enum": ["summary", "trend", "comparison"]}
                    },
                    "required": ["data"]
                }
            )
        ]
        for skill in builtin_skills:
            db.add(skill)
        
        await db.commit()
        
        print(f"[OK] Created tenant: {tenant.name} (id: {tenant.id})")
        print(f"[OK] Created admin user: {admin_user.email}")
        print(f"[OK] Created sample app: {sample_app.name}")
        print(f"[OK] Created API key: {master_key}")
        print(f"[OK] Created {len(builtin_skills)} builtin skills")


async def main():
    """Initialize database and seed data"""
    print("=" * 60)
    print("SmartLink Database Initialization")
    print("=" * 60)
    
    try:
        # Create all tables
        print("\n[1/2] Creating database tables...")
        await init_db()
        print("[OK] All tables created successfully")
        
        # Seed initial data
        print("\n[2/2] Seeding initial data...")
        await seed_initial_data()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Database initialization complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize database: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())