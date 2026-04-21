"""
创建测试数据 - Tenant, User, Agent, API Key
用于测试完整的 WebSocket 流程和认证系统
"""
import asyncio
import bcrypt  # Use bcrypt directly to avoid passlib compatibility issues
from sqlalchemy import select
from db.session import async_session_maker
from models import (
    Tenant, User, Agent, APIKey,
    TenantStatus, AgentTypeEnum as AgentType, AgentStatus, UserRole
)
from services.auth_service import AuthService


def hash_password_bcrypt(password: str) -> str:
    """Hash password using bcrypt directly"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def create_test_data():
    """创建测试租户、用户、Agent 和 API Key"""
    async with async_session_maker() as db:
        auth_service = AuthService(db)
        
        # 1. 获取或创建 Tenant
        result = await db.execute(select(Tenant).where(Tenant.slug == "test"))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                name="Test Tenant",
                slug="test",
                status=TenantStatus.ACTIVE
            )
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)
            print(f"[OK] Tenant created: {tenant.id}")
        else:
            print(f"[OK] Tenant exists: {tenant.id}")
        
        # 2. 创建 Test User
        result = await db.execute(select(User).where(User.email == "test@test.com"))
        user = result.scalar_one_or_none()
        
        if not user:
            # Use bcrypt directly to avoid passlib/bcrypt version compatibility issues
            password_hash = hash_password_bcrypt("test123")
            user = User(
                tenant_id=tenant.id,
                email="test@test.com",
                full_name="Test User",
                role=UserRole.ADMIN,
                password_hash=password_hash,
                is_active=True,
                is_verified=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"[OK] User created: {user.id}")
        else:
            print(f"[OK] User exists: {user.id}")
        
        # 3. 创建 Test Agent
        result = await db.execute(select(Agent).where(Agent.code == "test_assistant"))
        agent = result.scalar_one_or_none()
        
        if not agent:
            agent = Agent(
                tenant_id=tenant.id,
                name="测试助手",
                code="test_assistant",
                type=AgentType.CUSTOM,
                status=AgentStatus.ACTIVE,
                persona="你是一个测试助手，用于验证 WebSocket 连接和 Agent 执行流程。",
                welcome_message="您好！我是测试助手，请问有什么可以帮您？",
                # Responsibilities should be objects with proper structure
                responsibilities=[
                    {"id": "resp_1", "name": "回答问题", "description": "回答用户问题", "priority": 1, "keywords": ["问题", "咨询"], "examples": []},
                    {"id": "resp_2", "name": "测试 WebSocket", "description": "测试 WebSocket 连接", "priority": 2, "keywords": ["WebSocket", "测试"], "examples": []}
                ],
                mcp_servers=[],
                skills=["web_search"],
                tools=[],
                llm_config={
                    "provider": "openai",
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "maxTokens": 4096
                }
            )
            db.add(agent)
            await db.commit()
            await db.refresh(agent)
            print(f"[OK] Agent created: {agent.id}")
        else:
            print(f"[OK] Agent exists: {agent.id}")
        
        # 4. 创建 API Key
        raw_api_key = auth_service.generate_api_key()
        key_hash = auth_service.hash_api_key(raw_api_key)
        
        new_key = APIKey(
            tenant_id=tenant.id,
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=raw_api_key[:8],
            name="Test API Key",
            description="API Key for WebSocket testing",
            is_active=True,
            scopes=["*"],
            rate_limit=100
        )
        db.add(new_key)
        await db.commit()
        
        print(f"[OK] API Key created: {raw_api_key}")
        
        # 5. 生成 JWT Token
        permissions = await auth_service.get_user_permissions(user)
        token = auth_service.create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            role=user.role.value,
            email=user.email,
            permissions=permissions
        )
        print(f"[OK] JWT Token: {token[:50]}...")
        
        return {
            "tenant_id": tenant.id,
            "user_id": user.id,
            "agent_id": agent.id,
            "agent_code": agent.code,
            "api_key": raw_api_key,
            "jwt_token": token
        }


async def verify_agentscope_components():
    """验证 AgentScope 组件是否正常加载"""
    print("\n=== Verifying AgentScope Components ===")
    
    # 1. 验证 AgentHub
    try:
        from agent.agentscope.hub import AgentHub
        hub = AgentHub.get_instance()
        print(f"[OK] AgentHub loaded: {type(hub).__name__}")
        print(f"     - participants: {len(hub.participants)}")
        print(f"     - message_history: {len(hub.message_history)}")
    except ImportError as e:
        print(f"[FAIL] AgentHub import failed: {e}")
    except Exception as e:
        print(f"[FAIL] AgentHub initialization failed: {e}")
    
    # 2. 验证 AgentFactory
    try:
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        print(f"[OK] AgentFactory loaded: {type(factory).__name__}")
        print(f"     - model_configs: {list(factory._model_configs.keys())}")
        
        # Test building system prompt
        test_prompt = factory._build_sys_prompt(
            identity={
                "name": "Test Agent",
                "persona": "You are a test agent.",
                "responsibilities": ["Answer questions", "Test WebSocket"]
            },
            variables={}
        )
        print(f"     - prompt preview: {test_prompt[:100]}...")
    except ImportError as e:
        print(f"[FAIL] AgentFactory import failed: {e}")
    except Exception as e:
        print(f"[FAIL] AgentFactory initialization failed: {e}")
    
    # 3. 验证 AgentToolkit
    try:
        from agent.agentscope.toolkit import AgentToolkit
        toolkit = AgentToolkit()
        print(f"[OK] AgentToolkit loaded: {type(toolkit).__name__}")
        schemas = toolkit.get_tool_schemas()
        print(f"     - tool schemas: {len(schemas)} tools registered")
    except ImportError as e:
        print(f"[FAIL] AgentToolkit import failed: {e}")
    except Exception as e:
        print(f"[FAIL] AgentToolkit initialization failed: {e}")
    
    # 4. 验证 Skill Registry
    try:
        from agent.skills.base import skill_registry
        registered_skills = list(skill_registry._skills.keys())
        print(f"[OK] SkillRegistry loaded: {len(registered_skills)} skills")
        print(f"     - registered: {registered_skills}")
    except ImportError as e:
        print(f"[FAIL] SkillRegistry import failed: {e}")
    except Exception as e:
        print(f"[FAIL] SkillRegistry initialization failed: {e}")
    
    # 5. 验证 Orchestrator
    try:
        from agent.core.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator(config={})
        print(f"[OK] AgentOrchestrator loaded: {type(orchestrator).__name__}")
    except ImportError as e:
        print(f"[FAIL] AgentOrchestrator import failed: {e}")
    except Exception as e:
        print(f"[FAIL] AgentOrchestrator initialization failed: {e}")


async def main():
    """Main entry point"""
    print("=" * 60)
    print("SmartLink Test Data Creation")
    print("=" * 60)
    
    try:
        # Create test data
        print("\n[1] Creating test data...")
        result = await create_test_data()
        
        # Verify AgentScope components
        print("\n[2] Verifying AgentScope components...")
        await verify_agentscope_components()
        
        # Print credentials
        print("\n" + "=" * 60)
        print("=== Test Credentials ===")
        print("=" * 60)
        print(f"Tenant ID:     {result['tenant_id']}")
        print(f"User ID:       {result['user_id']}")
        print(f"Agent ID:      {result['agent_id']}")
        print(f"Agent Code:    {result['agent_code']}")
        print(f"API Key:       {result['api_key']}")
        print(f"JWT Token:     {result['jwt_token'][:80]}...")
        print("=" * 60)
        
        # WebSocket test instructions
        print("\n=== WebSocket Test Instructions ===")
        print("Use the following URL to connect:")
        print(f"  ws://localhost:8000/smart-link-service/api/v1/ws/chat/test-client?api_key={result['api_key']}")
        print("\nOr with JWT token:")
        print(f"  ws://localhost:8000/smart-link-service/api/v1/ws/chat/test-client?token={result['jwt_token']}")
        print("\nSend test message:")
        print('''  {"type": "chat", "data": {"message": "你好"}}''')
        
        return result
        
    except Exception as e:
        print(f"\n[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())