# SmartLink 服务启动优化方案

**生成日期**: 2026-04-21  
**研究目标**: 分析服务启动瓶颈，提出优化方案  
**当前启动时间**: 3-20秒（取决于 MCP servers 数量）

---

## 一、启动流程分析

### 1.1 当前启动序列

```
gateway/main.py lifespan()

┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 0: MODULE IMPORT (Before lifespan)                                │
│ ├─ Skill auto-discovery (agent/skills/base.py)                         │
│ │  → Scans agent/skills/builtin/ directory                             │
│ │  → Uses pkgutil.iter_modules + importlib                             │
│ │  Impact: ~100-200ms (2 skills currently)                             │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 1: DATABASE INIT                                                  │
│ ├─ await init_db() (db/session.py:96-98)                               │
│ │  → Base.metadata.create_all()                                        │
│ │  → Creates ALL tables on EVERY startup                               │
│ │  Impact: 200ms-2000ms                                                │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 2: REDIS CONNECTION                                               │
│ ├─ manager.init_redis()                                                 │
│ │  → Creates Redis connection pool                                     │
│ │  Impact: 20-100ms                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 3: SESSION MANAGER                                                │
│ ├─ session_manager.connect()                                            │
│ │  Impact: 10-50ms                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 4: REDIS-DEPENDENT SERVICES                                       │
│ ├─ init_lane_registry()    → <10ms                                     │
│ ├─ init_router()           → <10ms                                     │
│ ├─ init_heartbeat_manager()→ <10ms                                     │
│ ├─ init_distribution()     → <10ms                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 5: MODEL RESOLVER                                                 │
│ ├─ init_model_resolver()    → <5ms                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 6: OAUTH PROVIDERS                                                │
│ ├─ ProviderRegistry.configure() → <5ms per provider                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Phase 7: MCP SERVERS ⚠️ CRITICAL BOTTLENECK                            │
│ ├─ load_mcp_servers()                                                   │
│ │  → Source 1: Database (SELECT MCPServer WHERE status=ACTIVE)        │
│ │  → Source 2: Config file (config/mcp_servers.yml)                   │
│ │  → Source 3: Environment (MCP_SERVERS_URL)                          │
│ │  🔴 SEQUENTIAL awaiting - each server blocks startup                 │
│ │  Impact: 500ms-15000ms+ PER SERVER                                   │
└─────────────────────────────────────────────────────────────────────────┘

TOTAL: 0.4s (fast) → 20s+ (with MCP servers)
```

### 1.2 瓶颈识别

| 瓶颈 | 级别 | 原因 | 影响 |
|------|------|------|------|
| **MCP Server 加载** | 🔴 高 | 顺序连接，每个 await 阻塞 | 5-15s+ |
| **Database init** | 🟡 中 | 每次创建所有表，无版本跟踪 | 0.2-2s |
| **Skill discovery** | 🟡 低 | import time 运行，无缓存 | 0.1-0.5s |
| Redis/Session/etc | 🟢 低 | 快速异步操作 | <0.1s |

---

## 二、优化方案

### 2.1 Tier 1: 最高影响（50-80% 减少）

#### 优化 1: MCP Server 并行加载 + Lazy Connection

**当前问题**:
```python
# gateway/main.py:59-74（当前）
for server in db_servers.scalars().all():  # 🔴 顺序迭代
    client = await mcp_manager.register_client(...)  # 🔴 阻塞
    await toolkit.register_mcp_server(client)  # 🔴 阻塞
```

**优化方案**:
```python
# gateway/main.py（优化后）
import asyncio
from typing import List, Dict, Any

async def load_mcp_servers() -> AgentToolkit:
    """
    Load MCP servers with lazy initialization.
    
    Returns toolkit immediately, connects servers in background.
    """
    toolkit = AgentToolkit()
    
    # Collect configs (fast, doesn't block)
    configs = await _collect_mcp_configs()
    
    # Store configs for lazy connection
    app.state.mcp_configs = configs
    app.state.mcp_pending = set(c['name'] for c in configs)
    
    # Background task: connect servers (doesn't block startup)
    asyncio.create_task(_connect_mcp_servers_background(toolkit, configs))
    
    return toolkit


async def _collect_mcp_configs() -> List[Dict[str, Any]]:
    """
    Collect all MCP server configs from sources.
    
    Fast operation - only queries, doesn't connect.
    """
    configs = []
    
    async with async_session_maker() as session:
        # 1. Database
        db_servers = await session.execute(
            select(MCPServer).where(MCPServer.status == ResourceStatus.ACTIVE)
        )
        for server in db_servers.scalars().all():
            configs.append({
                "name": str(server.name),
                "type": str(server.type) or "stdio",
                "source": "database",
                **(server.config or {}),
                "endpoint": str(server.endpoint) if server.endpoint else None
            })
        
        # 2. Config file
        config_file = os.path.join(os.getcwd(), "config", "mcp_servers.yml")
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            for server_config in config_data.get('mcp_servers', []):
                if server_config:
                    configs.append({
                        "name": server_config.get('name', 'unknown'),
                        "source": "config_file",
                        **server_config
                    })
        
        # 3. Environment
        if settings.MCP_SERVERS_URL:
            for url in settings.MCP_SERVERS_URL.split(','):
                url = url.strip()
                if url:
                    name = url.split('/')[-1] or 'unknown'
                    configs.append({
                        "name": name,
                        "type": "http",
                        "endpoint": url,
                        "source": "environment"
                    })
    
    return configs


async def _connect_mcp_servers_background(
    toolkit: AgentToolkit,
    configs: List[Dict[str, Any]]
):
    """
    Connect MCP servers in background with parallel execution.
    
    - Parallel connections (asyncio.gather)
    - Timeout protection (5s per server)
    - Graceful failure handling
    """
    print(f"[MCP] Background connecting {len(configs)} servers...")
    
    tasks = [
        _connect_single_server_safe(toolkit, config)
        for config in configs
    ]
    
    # Parallel execution with exception handling
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Log results
    connected = 0
    for i, result in enumerate(results):
        config_name = configs[i].get('name', 'unknown')
        if isinstance(result, Exception):
            print(f"[MCP] ❌ Failed: {config_name} - {str(result)[:100]}")
        else:
            connected += 1
            print(f"[MCP] ✅ Connected: {config_name}")
    
    print(f"[MCP] Summary: {connected}/{len(configs)} servers connected")


async def _connect_single_server_safe(
    toolkit: AgentToolkit,
    config: Dict[str, Any]
) -> bool:
    """
    Connect single MCP server with timeout protection.
    """
    name = config.get('name', 'unknown')
    
    try:
        # Timeout: 5 seconds per server
        client = await asyncio.wait_for(
            mcp_manager.register_client(name, config),
            timeout=5.0
        )
        
        await asyncio.wait_for(
            toolkit.register_mcp_server(client),
            timeout=3.0
        )
        
        # Update pending list
        if hasattr(app.state, 'mcp_pending'):
            app.state.mcp_pending.discard(name)
        
        return True
        
    except asyncio.TimeoutError:
        raise Exception(f"Connection timeout ({5}s)")
    except Exception as e:
        raise e


# Lazy connection helper (for first request)
async def ensure_mcp_connected(name: str) -> Optional[MCPClient]:
    """
    Ensure MCP server is connected (lazy connect on demand).
    
    Use in request handlers when MCP tools are needed.
    """
    # Check if already connected
    if name not in app.state.mcp_pending:
        return mcp_manager.get_client(name)
    
    # Connect now (lazy)
    config = next(
        (c for c in app.state.mcp_configs if c['name'] == name),
        None
    )
    
    if not config:
        return None
    
    try:
        client = await mcp_manager.register_client(name, config)
        await toolkit.register_mcp_server(client)
        app.state.mcp_pending.discard(name)
        return client
    except Exception:
        return None
```

**预期效果**:
- 启动时间: 15s → 1s（立即可用）
- MCP 连接: 后台并行执行
- 失败保护: 单个 server 失败不影响其他

---

#### 优化 2: Background Initialization

**当前问题**: 所有初始化都在 yield 前执行，阻塞启动。

**优化方案**:
```python
# gateway/main.py lifespan 优化
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Optimized lifespan with background initialization.
    
    Phase 1 (blocking): Critical resources
    Phase 2 (background): Non-critical services
    """
    
    # ========== PHASE 1: CRITICAL (阻塞启动) ==========
    print(f"[START] Starting {settings.APP_NAME} v{settings.VERSION}")
    
    # Database (必须)
    print("[DB] Initializing database...")
    await init_db_fast()  # 优化版本
    print("[OK] Database ready")
    
    # Redis (必须)
    print("[REDIS] Connecting...")
    try:
        await manager.init_redis()
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        print("[OK] Redis connected")
    except Exception as e:
        if settings.is_development:
            print(f"[WARN] Redis failed (dev mode): {str(e)[:100]}")
            redis_client = None
        else:
            raise
    
    # ========== 启动完成，接受请求 ==========
    print(f"[READY] ✅ {settings.APP_NAME} is ready to accept requests!")
    yield
    
    # ========== PHASE 2: NON-CRITICAL (后台执行) ==========
    print("[BG] Starting background initialization...")
    
    # MCP servers (后台)
    asyncio.create_task(_init_mcp_background(app))
    
    # Session manager (后台)
    if redis_client:
        asyncio.create_task(_init_session_background(app, redis_client))
    
    # Skill validation (后台)
    asyncio.create_task(_validate_skills_background(app))
    
    # LLM cache warmup (后台)
    asyncio.create_task(_warm_llm_cache_background(app))
    
    # ========== SHUTDOWN ==========
    print(f"[STOP] Shutting down {settings.APP_NAME}")
    
    await mcp_manager.disconnect_all()
    if redis_client:
        await session_manager.disconnect()
        await manager.close()
    await close_db()
    
    print("[BYE] Goodbye!")


# Background init helpers
async def _init_mcp_background(app: FastAPI):
    """后台 MCP 初始化"""
    toolkit = await load_mcp_servers()
    app.state.toolkit = toolkit
    print("[BG] ✅ MCP servers initialized")


async def _init_session_background(app: FastAPI, redis_client):
    """后台 Session/Lane/Distribution 初始化"""
    await session_manager.connect()
    await init_lane_registry(redis_client)
    await init_router(redis_client)
    await init_heartbeat_manager(redis_client)
    await init_distribution(redis_client)
    print("[BG] ✅ Session/Lane/Distribution initialized")


async def _validate_skills_background(app: FastAPI):
    """后台 Skill 验证"""
    # Validate skill configurations
    pass


async def _warm_llm_cache_background(app: FastAPI):
    """后台 LLM 缓存预热"""
    # Warm up common prompts
    pass


async def init_db_fast():
    """
    Fast database initialization.
    
    - Check if tables exist (skip if yes)
    - Only create missing tables
    """
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        # Check existing tables (SQLite)
        if settings.DATABASE_TYPE == "sqlite":
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            existing = set(row[0] for row in result)
        else:
            # PostgreSQL
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            )
            existing = set(row[0] for row in result)
        
        # Required tables
        required = set(Base.metadata.tables.keys())
        
        # Only create missing tables
        if existing >= required:
            print("[DB] All tables exist, skipping creation")
            return
        
        missing = required - existing
        if missing:
            print(f"[DB] Creating {len(missing)} missing tables...")
            await conn.run_sync(Base.metadata.create_all)
```

---

### 2.2 Tier 2: 中等影响（20-40% 减少）

#### 优化 3: Skill Discovery 缓存

**当前问题**:
```python
# agent/skills/base.py:160-191
class SkillRegistry:
    def __init__(self):
        self._auto_discover()  # 🔴 每次运行

skill_registry = SkillRegistry()  # 🔴 import time
```

**优化方案**:
```python
# agent/skills/base.py
import json
import hashlib
from pathlib import Path

class SkillRegistry:
    CACHE_DIR = Path(".cache")
    CACHE_FILE = CACHE_DIR / "skill-discovery.json"
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._loaded = False
        
        # Ensure cache directory
        self.CACHE_DIR.mkdir(exist_ok=True)
        
        # Try cache first
        if self._load_from_cache():
            print(f"[Skills] Loaded {len(self._skills)} from cache")
            self._loaded = True
        else:
            self._auto_discover()
            self._save_cache()
    
    def _get_code_hash(self) -> str:
        """
        Hash of builtin skills directory.
        
        Used to invalidate cache when skills change.
        """
        builtin_dir = Path(__file__).parent / "builtin"
        hasher = hashlib.md5()
        
        for py_file in builtin_dir.glob("*.py"):
            hasher.update(py_file.read_bytes())
        
        return hasher.hexdigest()
    
    def _load_from_cache(self) -> bool:
        """
        Load skills from disk cache.
        
        Returns True if cache is valid and loaded.
        """
        if not self.CACHE_FILE.exists():
            return False
        
        try:
            cached = json.loads(self.CACHE_FILE.read_text())
            
            # Validate cache version
            if cached.get("hash") != self._get_code_hash():
                print("[Skills] Cache invalid (code changed)")
                return False
            
            # Load cached skills metadata
            # Note: Still need to instantiate, but skip discovery
            for name, meta in cached.get("skills", {}).items():
                skill_class = self._get_skill_class(meta["module"], meta["class"])
                if skill_class:
                    self._skills[name] = skill_class()
            
            return len(self._skills) > 0
            
        except Exception as e:
            print(f"[Skills] Cache load failed: {e}")
            return False
    
    def _save_cache(self):
        """
        Save skill discovery results to cache.
        """
        cache_data = {
            "hash": self._get_code_hash(),
            "timestamp": time.time(),
            "skills": {
                name: {
                    "module": skill.__class__.__module__,
                    "class": skill.__class__.__name__,
                }
                for name, skill in self._skills.items()
            }
        }
        
        self.CACHE_FILE.write_text(json.dumps(cache_data, indent=2))
        print(f"[Skills] Saved {len(self._skills)} to cache")
    
    def _get_skill_class(self, module: str, class_name: str) -> Optional[type]:
        """
        Get skill class by module and name.
        """
        try:
            mod = importlib.import_module(module)
            return getattr(mod, class_name, None)
        except ImportError:
            return None
```

**预期效果**: 200ms → 10ms

---

#### 优化 4: Database Fast Init

**当前问题**:
```python
# db/session.py:96-98
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # 🔴 每次创建所有表
```

**优化方案**:
```python
# db/session.py
async def init_db():
    """
    Fast database initialization.
    
    - Check existing tables first
    - Only create missing tables
    - Skip if all tables exist
    """
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        # Get existing tables
        if settings.DATABASE_TYPE == "sqlite":
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            existing_tables = set(row[0] for row in result)
        else:
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
            )
            existing_tables = set(row[0] for row in result)
        
        # Get required tables
        required_tables = set(Base.metadata.tables.keys())
        
        # Check if all exist
        if existing_tables >= required_tables:
            print("[DB] ✅ All tables exist, skipping creation")
            return
        
        # Only create missing tables
        missing_tables = required_tables - existing_tables
        
        if missing_tables:
            print(f"[DB] Creating {len(missing_tables)} missing tables...")
            
            # Create only missing tables
            for table_name in missing_tables:
                table = Base.metadata.tables[table_name]
                await conn.run_sync(
                    lambda sync_conn: table.create(sync_conn, checkfirst=True)
                )
            
            print(f"[DB] ✅ Created {len(missing_tables)} tables")
```

**预期效果**: 2s → 50ms（表已存在时）

---

### 2.3 Tier 3: 较小影响（5-15% 减少）

#### 优化 5: Redis Connection Warmup

```python
# gateway/websocket/manager.py
async def warm_up_redis_pool(client: redis.Redis, target: int = 10):
    """
    Pre-warm Redis connection pool.
    
    Establishes target connections before accepting requests.
    """
    print(f"[REDIS] Warming up {target} connections...")
    await asyncio.gather(*[client.ping() for _ in range(target)])
    print(f"[REDIS] ✅ Pool warmed with {target} connections")


# In lifespan, after Redis connect:
await warm_up_redis_pool(redis_client, target=20)
```

#### 优化 6: Gunicorn Preload (生产环境)

```bash
# docker/start.sh 或生产启动脚本
gunicorn gateway.main:app \
    --workers 4 \
    --preload \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 30 \
    --keep-alive 5
```

**注意事项**:
- 仅生产环境使用
- 开发模式不能用（破坏热重载）
- 需确保所有连接在 lifespan 创建，而非 import time

---

## 三、实施计划

### 3.1 优先级排序

| 优先级 | 优化项 | 预期效果 | 复杂度 | 文件 |
|--------|--------|----------|--------|------|
| **P1** | MCP 并行 + 后台 | 15s→1s | 中 | gateway/main.py |
| **P2** | Background init | 立即可用 | 低 | gateway/main.py |
| **P3** | Skill discovery 缓存 | 200ms→10ms | 低 | agent/skills/base.py |
| **P4** | DB fast init | 2s→50ms | 低 | db/session.py |
| **P5** | Redis warmup | 首次更快 | 低 | gateway/websocket/manager.py |

### 3.2 实施步骤

```
Step 1: MCP 并行加载（30min）
├─ 修改 load_mcp_servers() 为后台任务
├─ 添加 _connect_mcp_servers_background()
├─ 添加 _connect_single_server_safe() with timeout
└─ 测试启动时间

Step 2: Background init（10min）
├─ 修改 lifespan yield 位置
├─ 移动非关键初始化到后台
└─ 测试启动时间

Step 3: Skill 缓存（15min）
├─ 添加 SkillRegistry._load_from_cache()
├─ 添加 SkillRegistry._save_cache()
├─ 添加 code hash validation
└─ 测试

Step 4: DB fast init（20min）
├─ 添加 init_db_fast()
├─ 添加 table existence check
└─ 测试

Step 5: Redis warmup（5min）
├─ 添加 warm_up_redis_pool()
└─ 测试
```

### 3.3 验证方法

```bash
# 测试启动时间
time uvicorn gateway.main:app --port 8000

# 期望结果：
# Before: 10-20s
# After:  <1s (启动立即可用)
```

---

## 四、参考资源

### 4.1 FastAPI Lifespan 最佳实践

- FastAPI Advanced User Guide: Lifespan Events
- https://fastapi.tiangolo.com/advanced/events/

### 4.2 MCP Lazy Initialization

- IBM MCP Context Forge Issue #2010
- https://github.com/IBM/mcp-context-forge/issues/2010

### 4.3 Plugin Discovery 缓存

- OpenClaw Optimization Pattern
- https://github.com/openclaw/openclaw/issues/67040

### 4.4 Redis Connection Warmup

- Oneuptime Blog: Redis Connection Warm-up
- https://oneuptime.com/blog/post/redis-connection-warm-up

---

## 五、总结

### 当前状态
- 启动时间: 3-20秒
- 主要瓶颈: MCP Server 顺序加载

### 优化后预期
- 启动时间: <1秒（立即可用）
- MCP 连接: 后台并行执行
- 失败保护: 单个失败不影响其他

### 关键改进
1. **并行化**: MCP servers 并行连接（asyncio.gather）
2. **后台化**: 非关键服务在 yield 后执行
3. **缓存化**: Skill discovery 结果缓存
4. **快速检查**: Database 只创建缺失表

---

**下一步**: 按优先级顺序实施优化，每次优化后测试启动时间。