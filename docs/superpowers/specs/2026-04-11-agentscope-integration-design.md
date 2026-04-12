# AgentScope 集成设计文档

## 文档信息

| 字段 | 值 |
|------|-----|
| 版本 | 1.0 |
| 状态 | 设计完成 |
| 日期 | 2026-04-11 |
| 作者 | SmartLink Team |

---

## 1. 概述

### 1.1 设计目标

将 AgentScope 框架集成到 SmartLink 平台，替换现有自研 orchestrator，实现：

1. 标准 Agent 编排能力（MessageHub + ReActAgent）
2. 统一工具管理（Toolkit）
3. 多 Agent 协作支持
4. 端到端测试验证

### 1.2 核心决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 集成模式 | 完全替换 | 减少自研成本，获得标准化能力 |
| 依赖来源 | PyPI 官方版 | 稳定性优先 |
| 集成范围 | MessageHub + ReActAgent + Toolkit | 核心三件套 |
| 代码处理 | 直接替换现有代码 | 最干净 |
| 测试策略 | 端到端集成测试 | TDD 验证完整流程 |

---

## 2. 依赖变更

### 2.1 pyproject.toml 更新

**新增依赖：**
- `agentscope>=0.1.0`

**保留依赖：**
- `litellm>=1.20.0`（AgentScope 内部支持）
- `mcp>=0.9.0`（Toolkit MCP 适配）

**移除依赖：**
- `langchain>=0.1.0`
- `langchain-community>=0.0.20`

---

## 3. 目录结构变更

### 3.1 新增目录

```
agent/agentscope/
├── __init__.py
├── hub.py          # MessageHub 配置
├── agent_factory.py # ReActAgent 创建工厂
└── toolkit.py      # Toolkit 注册
```

### 3.2 删除文件

- `agent/core/executor.py`（AgentScope Pipeline 替代）
- `agent/core/loop.py`（ReActAgent 内置循环）

### 3.3 重写文件

- `agent/core/orchestrator.py`（使用 AgentScope）

### 3.4 保留文件

- `agent/skills/builtin/`（改为 Toolkit 注册）
- `agent/mcp/client.py`（Toolkit MCP 适配）
- `agent/core/memory.py`（Phase 2 替换）

---

## 4. 核心组件设计

### 4.1 MessageHub（hub.py）

**AgentHub 类职责：**
- 单例模式管理 MsgHub
- 支持消息广播和点对点
- 消息历史记录

**关键方法：**
- `initialize(agents)` - 初始化 MsgHub
- `broadcast(message)` - 广播消息
- `send_to(recipient, message)` - 点对点发送

### 4.2 ReActAgent（agent_factory.py）

**AgentFactory 类职责：**
- 加载 LLM 配置（AgentScope 格式）
- 创建 ReActAgent 实例
- 根据 Agent Role 配置创建 SubAgent

**关键方法：**
- `create_agent(name, sys_prompt, toolkit)` - 创建 Agent
- `create_sub_agent(role_config, toolkit)` - 创建 SubAgent

### 4.3 Toolkit（toolkit.py）

**AgentToolkit 类职责：**
- 注册 Skills 为工具函数
- 注册 MCP Servers
- 提供 JSON Schema（用于 tool calling）

**关键方法：**
- `register_skill(skill)` - 注册 Skill
- `register_mcp_server(client)` - 注册 MCP
- `get_tool_schemas()` - 获取 JSON Schema

### 4.4 Orchestrator 重写

**核心方法：**
- `execute(agent_id, input_data)` - 单 Agent 执行
- `execute_stream(agent_id, input_data)` - 流式执行
- `execute_multi_agent(agents, input_data)` - 多 Agent 协作

---

## 5. WebSocket Handler 改造

### 5.1 消息协议

**客户端 → 服务端：**
- `init` - 初始化会话（agentId, sessionId）
- `chat` - 聊天消息（message, context）
- `tool_call` - 工具调用确认（toolName, arguments）
- `status` - 状态查询

**服务端 → 客户端：**
- `init_success` - 初始化成功
- `chunk` - 流式内容（content, done=false）
- `complete` - 完成标记（done=true）
- `tool_request` - 工具请求确认
- `error` - 错误消息

---

## 6. 测试设计

### 6.1 测试结构

```
tests/
├── integration/
│   └── test_agentscope_flow.py
├── unit/
│   ├── test_hub.py
│   ├── test_agent_factory.py
│   └── test_toolkit.py
├── fixtures/
│   ├── mock_agent_config.py
│   └── mock_llm_response.py
└── conftest.py
```

### 6.2 测试用例

| 测试用例 | 验证内容 |
|---------|---------|
| `test_basic_chat_flow` | 基本聊天流程 |
| `test_streaming_flow` | 流式响应 |
| `test_tool_calling_flow` | 工具调用 |
| `test_multi_agent_flow` | 多 Agent 协作 |
| `test_error_handling` | 错误处理 |
| `test_websocket_integration` | WebSocket 端点 |

---

## 7. 实施步骤

1. 更新 pyproject.toml（添加 agentscope 依赖）
2. 创建 agent/agentscope/ 模块
3. 实现 hub.py、agent_factory.py、toolkit.py
4. 重写 orchestrator.py
5. 修改 WebSocket handler
6. 删除 executor.py、loop.py
7. 创建测试文件
8. 运行测试验证
9. 更新 AGENTS.md

---

## 8. 成功标准

| 标准 | 验证方式 |
|------|---------|
| 所有测试通过 | pytest 执行 |
| WebSocket 端点正常 | TestClient 测试 |
| Agent 能执行任务 | 端到端测试 |
| 流式响应正常 | 流式测试 |
| 工具调用正确 | tool_calling 测试 |

---

**文档结束**
