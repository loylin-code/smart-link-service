# MCP Integration Gap Fix Design

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Fix implementation gaps against `2026-04-13-mcp-integration-design.md`
**Related:** Phase 4: MCP完整集成 (ARCHITECTURE-V2.md)

---

## 1. Overview

补齐现有 MCP 设计文档与实现的差距，确保 MCP 集成完全符合设计规范。

### 1.1 Gap Analysis Summary

| 模块 | 完成度 | Gap 类型 |
|------|--------|----------|
| MCP Client (3种传输) | 100% | ✅ 无差距 |
| AgentToolkit 集成 | 100% | ✅ 无差距 |
| REST API | 90% | ⚠️ 缺少 `/tools` 端点 |
| 数据模型 | 80% | ❌ 缺失字段 |
| Schema 一致性 | 60% | ❌ 不匹配 |
| 错误处理 | 40% | ❌ 无重试/恢复建议 |
| 配置示例 | 20% | ⚠️ 全部注释 |

**整体完成度：85%**

---

## 2. Task Breakdown

### Task 1: 数据模型字段补齐

**文件**: `models/application.py`

**新增字段**:

```python
class MCPServer(Base):
    __tablename__ = "mcp_servers"
    
    # ... existing fields (id, tenant_id, name, description, type, endpoint, config, status, tools, resources) ...
    
    # 新增字段
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    prompts = Column(JSON, default=list, nullable=False)  # MCP Prompts 缓存
```

**理由**:
- `last_connected_at`: 追踪最后成功连接时间，用于健康检查
- `last_error`: 存储最后错误信息，便于问题诊断
- `prompts`: MCP Protocol 支持 Prompts，设计文档要求缓存

**数据库迁移**: 需要创建 Alembic migration

---

### Task 2: Schema 一致性修复

**文件**: `schemas/mcp.py`

**问题**: `MCPServerResponse` 包含 `last_connected_at` 和 `last_error` 字段，但 Model 中无这些字段，会导致 `AttributeError`。

**修复方案**:

```python
class MCPServerResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: Optional[str] = None
    type: str = "stdio"
    endpoint: Optional[str] = None
    config: Dict[str, Any] = {}
    status: str = "active"
    tools: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []  # 新增
    last_connected_at: Optional[datetime] = None  # 新增
    last_error: Optional[str] = None  # 新增
    created_at: datetime
    updated_at: Optional[datetime] = None
```

---

### Task 3: 缺失 API 端点

**文件**: `gateway/api/v1/mcp_servers.py`

**新增端点**:

```python
@router.get("/{server_id}/tools")
async def get_mcp_server_tools(
    server_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """列出 MCP Server 可用的工具
    
    Args:
        server_id: MCP Server ID
        db: Database session
        
    Returns:
        工具列表，包含 name, description, inputSchema
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    if server.status != ResourceStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"MCP Server {server_id} is not active"
        )
    
    return {
        "data": {
            "tools": server.tools or [],
            "total": len(server.tools or [])
        }
    }
```

---

### Task 4: 错误重试逻辑

**文件**: `agent/mcp/client.py`

**设计**: 添加指数退避重试机制

**新增 Mixin 类**:

```python
class MCPRetryMixin:
    """MCP 重试机制 Mixin
    
    提供指数退避重试能力，用于 MCP Client 调用失败时自动重试
    """
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    
    def _is_retryable(self, error: Exception) -> bool:
        """判断错误是否可重试
        
        Args:
            error: 异常对象
            
        Returns:
            True 如果可以重试
        """
        # 网络错误、超时、5xx 状态码可重试
        retryable_types = [
            "ConnectionError",
            "TimeoutError",
            "HTTPStatusError"
        ]
        
        error_type = type(error).__name__
        if error_type in retryable_types:
            return True
        
        # HTTP 5xx 可重试
        if hasattr(error, 'response'):
            status = getattr(error.response, 'status_code', 0)
            if 500 <= status < 600:
                return True
        
        return False
    
    async def _retry_call(
        self,
        fn: callable,
        *args,
        **kwargs
    ) -> Any:
        """带重试的调用
        
        Args:
            fn: 要调用的异步函数
            args: 函数参数
            kwargs: 函数关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            最后一次失败时的异常
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                if not self._is_retryable(e):
                    raise
                
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay
                    )
                    await asyncio.sleep(delay)
        
        raise last_error
```

**应用到 Client 类**:

```python
class SSEMCPClient(MCPRetryMixin, MCPClient):
    """SSE MCP Client with retry support"""
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call tool with retry"""
        return await self._retry_call(
            self._call_tool_impl,
            name,
            arguments
        )
    
    async def _call_tool_impl(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Actual implementation"""
        response = await self.client.post(
            f"{self.endpoint}/tools/call",
            json={"name": name, "arguments": arguments}
        )
        return response.json().get("content", [])
```

---

### Task 5: 错误响应格式增强

**文件**: `core/exceptions.py`

**扩展 MCPError**:

```python
class MCPError(Exception):
    """MCP 错误异常
    
    Attributes:
        message: 错误消息
        suggestions: 恢复建议列表
        server_name: MCP Server 名称
        tool_name: 工具名称（可选）
    """
    
    def __init__(
        self,
        message: str,
        suggestions: List[str] = None,
        server_name: str = None,
        tool_name: str = None
    ):
        self.message = message
        self.suggestions = suggestions or []
        self.server_name = server_name
        self.tool_name = tool_name
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于 API 响应"""
        return {
            "error": self.message,
            "type": "mcp_error",
            "suggestions": self.suggestions,
            "server_name": self.server_name,
            "tool_name": self.tool_name
        }
```

**典型建议示例**:

```python
# 连接失败
MCPError(
    "Failed to connect to MCP server",
    suggestions=[
        "Check if the MCP server is running",
        "Verify endpoint URL is correct",
        "Check network connectivity"
    ],
    server_name="github"
)

# 工具调用失败
MCPError(
    "Tool execution failed",
    suggestions=[
        "Check tool parameters",
        "Verify tool is available",
        "Try reconnecting to MCP server"
    ],
    server_name="filesystem",
    tool_name="read_file"
)
```

---

### Task 6: 配置示例完善

**文件**: `config/mcp_servers.yml`

**修复**: 提供真实可用的配置示例

```yaml
# MCP Server Configuration Example
# 
# SmartLink 支持 3 种 MCP 传输类型:
# - stdio: 本地进程通信
# - sse: Server-Sent Events (HTTP)
# - streamable_http: HTTP POST/GET
#
# 配置文件、数据库、环境变量均可定义 MCP Server

mcp_servers:
  # 示例 1: 本地 stdio MCP Server (文件系统)
  - name: "filesystem"
    type: "stdio"
    command: "python"
    args: ["-m", "mcp_server_filesystem"]
    env:
      ALLOWED_DIRS: "/home/user/documents"
    status: "active"
  
  # 示例 2: SSE 远程 MCP Server (GitHub)
  - name: "github"
    type: "sse"
    endpoint: "https://mcp.github.com/sse"
    headers:
      Authorization: "Bearer ${GITHUB_TOKEN}"
    timeout: 30
    status: "active"
  
  # 示例 3: StreamableHttp MCP Server (自定义)
  - name: "custom_api"
    type: "streamable_http"
    endpoint: "https://api.example.com/mcp"
    headers:
      X-API-Key: "${CUSTOM_API_KEY}"
    status: "inactive"
```

---

## 3. Implementation Order

按 TDD 顺序实施：

```
Task 1: 数据模型字段补齐 → Migration → Tests
Task 2: Schema 一致性修复 → Tests
Task 3: 缺失 API 端点 → Tests
Task 4: 错误重试逻辑 → Tests
Task 5: 错误响应格式 → Tests
Task 6: 配置示例完善 → Tests
Verification: 全量测试 + 提交
```

---

## 4. Test Coverage Requirements

每个 Task 需要补充测试：

| Task | 新增测试 |
|------|----------|
| Task 1 | `test_mcp_server_model_fields.py` |
| Task 2 | `test_mcp_schema_consistency.py` |
| Task 3 | `test_mcp_tools_endpoint.py` |
| Task 4 | `test_mcp_retry_logic.py` |
| Task 5 | `test_mcp_error_suggestions.py` |
| Task 6 | `test_mcp_config_loading.py` |

---

## 5. File Modifications Summary

| 文件 | 修改类型 |
|------|----------|
| `models/application.py` | 新增字段 |
| `schemas/mcp.py` | 新增字段、修复一致性 |
| `gateway/api/v1/mcp_servers.py` | 新增端点 |
| `agent/mcp/client.py` | 新增重试逻辑 |
| `core/exceptions.py` | 扩展 MCPError |
| `config/mcp_servers.yml` | 更新示例 |
| `tests/unit/test_mcp_*.py` | 新增/更新测试 |

---

## 6. Success Criteria

- [ ] MCPServer 模型包含所有设计文档字段
- [ ] Schema 与 Model 完全匹配，无 AttributeError
- [ ] `/tools` API 端点可用
- [ ] MCP Client 失败时自动重试（指数退避）
- [ ] MCPError 包含 suggestions 字段
- [ ] 配置文件示例可实际使用
- [ ] 所有新增测试 PASS

---

**Document Status:** Approved
**Next Step:** Invoke writing-plans skill to create implementation plan