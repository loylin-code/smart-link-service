# Agent Design API Design Specification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan after user approves this spec.

**Created:** 2026-04-13
**Status:** Draft
**Related:** Frontend AgentOrchestration.vue, AgentDesignPage.vue, services/agent.ts

---

## 1. Overview

### 1.1 Purpose

Create dedicated `/api/v1/agent-design` API for Agent design editing, separated from runtime `/agents` API. Supports frontend visual editor for:

- **Schema编排** - PageSchema component tree management
- **能力配置** - MCP/Skill/Tool/LLM binding
- **知识库配置** - Document/Database/API sources
- **验证预览** - Design validation and preview execution

### 1.2 Architecture

```
Frontend (AgentDesignPage.vue)
    ↓ HTTP/WebSocket
/api/v1/agent-design/{agent_id}/
    ├── schema          → PageSchema CRUD
    ├── capabilities    → MCP/Skill/Tool/LLM config
    ├── knowledge       → Knowledge source config
    ├── validate        → Design validation
    └── preview         → Preview execution

/api/v1/agents/         → Runtime API (existing)
    ├── CRUD            → Agent list/detail/create/update/delete
    ├── activate/pause  → Status management
    └── run             → Execution
```

### 1.3 Key Design Principles

- **Separation of Concerns** - Design API vs Runtime API
- **Schema-First** - Match frontend PageSchema structure exactly
- **Full Replacement** - Schema updates are full replacements (not partial merges)
- **Validation Before Save** - Validate design before persisting

---

## 2. API Endpoints

### 2.1 Schema Management

#### GET `/agent-design/{agent_id}/schema`

Get Agent's PageSchema.

**Response:**
```json
{
  "code": 200,
  "data": {
    "id": "schema_xxx",
    "version": "1.0.0",
    "root": {
      "id": "root",
      "type": "SlContainer",
      "props": { "static": { "direction": "vertical" } },
      "children": [...]
    },
    "styles": [],
    "scripts": []
  }
}
```

#### PUT `/agent-design/{agent_id}/schema`

Update Agent's PageSchema (full replacement).

**Request Body:**
```json
{
  "schema": {
    "id": "schema_xxx",
    "version": "1.0.0",
    "root": { ... }
  }
}
```

**Response:**
```json
{
  "code": 200,
  "data": { "success": true, "version": "1.0.0" }
}
```

#### POST `/agent-design/{agent_id}/schema/components`

Add component node to schema.

**Request Body:**
```json
{
  "parentId": "root",
  "component": {
    "id": "node_new",
    "type": "SlChatInterface",
    "props": { "static": { "title": "智能客服" } },
    "position": { "x": 100, "y": 200 }
  }
}
```

#### PUT `/agent-design/{agent_id}/schema/components/{node_id}`

Update single component node.

**Request Body:**
```json
{
  "props": { "static": { "title": "更新标题" } },
  "events": [{ "event": "click", "handler": { "type": "builtin", "action": "navigate" }}]
}
```

#### DELETE `/agent-design/{agent_id}/schema/components/{node_id}`

Delete component node and its children.

---

### 2.2 Capabilities Configuration

#### PUT `/agent-design/{agent_id}/capabilities`

Update Agent capabilities (MCP/Skill/Tool/LLM).

**Request Body:**
```json
{
  "mcpServers": [
    {
      "serverId": "mcp_weather",
      "required": true,
      "fallbackAction": "error",
      "customConfig": {}
    }
  ],
  "skills": [
    {
      "skillId": "skill_data_analysis",
      "version": "1.0.0",
      "enabled": true,
      "parameters": { "outputFormat": "json" }
    }
  ],
  "tools": [
    { "toolId": "web_search", "enabled": true, "parameters": {} }
  ],
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "maxTokens": 4096,
    "topP": 1,
    "systemPrompt": "你是一个智能客服助手..."
  }
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "success": true,
    "capabilities": {
      "mcpServers": 1,
      "skills": 1,
      "tools": 1,
      "llm": "gpt-4"
    }
  }
}
```

---

### 2.3 Knowledge Configuration

#### PUT `/agent-design/{agent_id}/knowledge`

Update Agent knowledge sources.

**Request Body:**
```json
{
  "documents": [
    {
      "id": "doc_1",
      "name": "产品手册",
      "type": "file",
      "source": "/data/docs/manual.pdf",
      "enabled": true
    }
  ],
  "databases": [
    {
      "id": "db_1",
      "name": "用户数据库",
      "type": "postgresql",
      "connectionString": "postgresql://...",
      "enabled": false
    }
  ],
  "apis": [
    {
      "id": "api_1",
      "name": "订单API",
      "endpoint": "https://api.example.com/orders",
      "method": "GET",
      "enabled": true
    }
  ],
  "searchConfig": {
    "enabled": true,
    "topK": 10,
    "similarityThreshold": 0.7,
    "rerankEnabled": false
  }
}
```

---

### 2.4 Validation & Preview

#### POST `/agent-design/{agent_id}/validate`

Validate Agent design before saving.

**Response:**
```json
{
  "code": 200,
  "data": {
    "valid": true,
    "warnings": [
      { "type": "missing_connection", "message": "MCP server 'weather' not connected" }
    ],
    "errors": []
  }
}
```

#### POST `/agent-design/{agent_id}/preview`

Preview execution with test input.

**Request Body:**
```json
{
  "input": { "message": "你好" },
  "mockMode": true
}
```

**Response:**
```json
{
  "code": 200,
  "data": {
    "previewId": "preview_xxx",
    "executionPlan": [
      { "step": 1, "agent": "main", "action": "llm_call" },
      { "step": 2, "agent": "main", "action": "tool_call", "tool": "web_search" }
    ],
    "estimatedTokens": 500
  }
}
```

---

## 3. Schema Structures

### 3.1 PageSchema (Frontend Match)

```typescript
interface PageSchema {
  id: string                  // Schema unique ID
  version: string             // Schema version '1.0.0'
  root: ComponentNode         // Component tree root
  styles?: StyleDefinition[]  // Global styles
  scripts?: ScriptDefinition[] // Custom scripts
}

interface ComponentNode {
  id: string
  type: string                // Component type: 'SlContainer', 'SlChatInterface', etc.
  name?: string               // Display name
  props?: {
    static?: Record<string, any>       // Static props
    bindings?: Record<string, ExpressionBinding>  // Expression bindings
    models?: Record<string, StateBinding>         // State bindings
  }
  style?: StyleConfig         // CSS styles
  condition?: ExpressionBinding // Conditional rendering
  loop?: LoopConfig           // Loop rendering
  events?: EventBinding[]     // Event handlers
  slots?: Record<string, SlotContent> // Slot content
  children?: ComponentNode[]  // Child components
  position?: { x: number; y: number } // Free layout position
}

interface EventBinding {
  event: string               // Event name: 'click', 'change', 'submit'
  handler: {
    type: 'builtin' | 'custom' | 'api' | 'state'
    action?: BuiltinAction    // 'navigate', 'openModal', 'submitForm', etc.
    code?: string             // Custom JS code
    api?: ApiCallConfig       // API call config
    stateUpdate?: StateUpdateConfig // State update config
    params?: Record<string, any>
  }
}
```

### 3.2 AgentCapabilities (Frontend Match)

```typescript
interface AgentCapabilities {
  mcpServers: MCPServerBinding[]
  skills: SkillBinding[]
  tools: ToolBinding[]
  llm: AgentLLMConfig
}

interface MCPServerBinding {
  serverId: string
  required: boolean
  fallbackAction: 'skip' | 'error' | 'wait'
  customConfig?: Record<string, unknown>
}

interface SkillBinding {
  skillId: string
  version: string
  enabled: boolean
  parameters: Record<string, unknown>
}

interface ToolBinding {
  toolId: string
  enabled: boolean
  parameters?: Record<string, unknown>
}

interface AgentLLMConfig {
  provider: string            // 'openai', 'anthropic', etc.
  model: string               // 'gpt-4', 'claude-3', etc.
  temperature: number         // 0.0 - 2.0
  maxTokens: number           // Max output tokens
  topP: number                // 0.0 - 1.0
  systemPrompt?: string       // System prompt
}
```

### 3.3 AgentKnowledge (Frontend Match)

```typescript
interface AgentKnowledge {
  documents: DocumentSource[]
  databases: DatabaseSource[]
  apis: APISource[]
  searchConfig: SearchConfig
}

interface DocumentSource {
  id: string
  name: string
  type: 'file' | 'url' | 'text'
  source: string              // File path, URL, or text content
  enabled: boolean
}

interface DatabaseSource {
  id: string
  name: string
  type: 'mysql' | 'postgresql' | 'mongodb' | 'redis'
  connectionString: string
  enabled: boolean
}

interface APISource {
  id: string
  name: string
  endpoint: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  headers?: Record<string, string>
  enabled: boolean
}

interface SearchConfig {
  enabled: boolean
  topK: number
  similarityThreshold: number
  rerankEnabled: boolean
}
```

---

## 4. Backend Implementation

### 4.1 File Structure

| File | Action | Purpose |
|------|--------|---------|
| `gateway/api/v1/agent_design.py` | Create | Design API endpoints |
| `gateway/api/v1/__init__.py` | Modify | Register agent_design router |
| `services/agent_design_service.py` | Create | Design service logic |
| `schemas/agent_design.py` | Create | Pydantic schemas for design |
| `models/agent.py` | Modify | Add page_schema, capabilities, knowledge JSON fields |
| `agent/core/schema_validator.py` | Create | Schema validation logic |
| `tests/unit/test_agent_design.py` | Create | Unit tests |

### 4.2 Agent Model Extensions

```python
# models/agent.py - Add JSON fields for design config

class Agent(Base):
    # ... existing fields
    
    # Design Configuration (JSON fields)
    page_schema = Column(JSON, default=dict, nullable=True)
    capabilities = Column(JSON, default=dict, nullable=True)
    knowledge = Column(JSON, default=dict, nullable=True)
```

### 4.3 Service Layer

```python
# services/agent_design_service.py

class AgentDesignService:
    async def get_schema(self, agent_id: str) -> dict:
        """Get Agent's PageSchema"""
        
    async def update_schema(self, agent_id: str, schema: dict) -> bool:
        """Update Agent's PageSchema (full replacement)"""
        
    async def add_component(self, agent_id: str, parent_id: str, component: dict) -> str:
        """Add component node to schema"""
        
    async def update_component(self, agent_id: str, node_id: str, updates: dict) -> bool:
        """Update single component"""
        
    async def delete_component(self, agent_id: str, node_id: str) -> bool:
        """Delete component and children"""
        
    async def update_capabilities(self, agent_id: str, capabilities: dict) -> bool:
        """Update MCP/Skill/Tool/LLM config"""
        
    async def update_knowledge(self, agent_id: str, knowledge: dict) -> bool:
        """Update knowledge sources"""
        
    async def validate_design(self, agent_id: str) -> dict:
        """Validate design configuration"""
        
    async def preview_execution(self, agent_id: str, input: dict) -> dict:
        """Preview execution plan"""
```

---

## 5. Validation Rules

### 5.1 Schema Validation

- **Component type** must be valid (from registry)
- **Required props** must be present
- **Event handlers** must have valid action type
- **No circular references** in component tree
- **Position bounds** within canvas limits

### 5.2 Capabilities Validation

- **MCP server** must exist and be connected
- **Skill** must exist with matching version
- **Tool** must be registered
- **LLM model** must be available

### 5.3 Knowledge Validation

- **Document source** must be accessible
- **Database connection** must be valid (if enabled)
- **API endpoint** must be reachable (if enabled)

---

## 6. Frontend Integration

### 6.1 API Service Update

```typescript
// app/src/services/agent.ts - Add design endpoints

export const agentApi = {
  // ... existing endpoints
  
  // Design API
  async getDesignSchema(agentId: string): Promise<PageSchema> {
    const response = await http.get(`/agent-design/${agentId}/schema`)
    return response.data.data
  },
  
  async updateDesignSchema(agentId: string, schema: PageSchema): Promise<boolean> {
    const response = await http.put(`/agent-design/${agentId}/schema`, { schema })
    return response.data.data.success
  },
  
  async updateCapabilities(agentId: string, capabilities: AgentCapabilities): Promise<boolean> {
    const response = await http.put(`/agent-design/${agentId}/capabilities`, capabilities)
    return response.data.data.success
  },
  
  async updateKnowledge(agentId: string, knowledge: AgentKnowledge): Promise<boolean> {
    const response = await http.put(`/agent-design/${agentId}/knowledge`, knowledge)
    return response.data.data.success
  },
  
  async validateDesign(agentId: string): Promise<ValidationResult> {
    const response = await http.post(`/agent-design/${agentId}/validate`)
    return response.data.data
  }
}
```

---

## 7. Test Coverage

| Test | Purpose |
|------|---------|
| `test_get_schema` | GET schema returns PageSchema |
| `test_update_schema` | PUT schema updates full schema |
| `test_add_component` | POST component adds to tree |
| `test_update_component` | PUT component updates node |
| `test_delete_component` | DELETE removes node |
| `test_update_capabilities` | PUT capabilities updates config |
| `test_update_knowledge` | PUT knowledge updates sources |
| `test_validate_design` | POST validate returns warnings/errors |
| `test_preview_execution` | POST preview returns execution plan |

---

## 8. Self-Review Checklist

| Item | Status |
|------|--------|
| Placeholder scan | ✅ No TBD/TODO |
| Internal consistency | ✅ All schemas match frontend |
| Scope check | ✅ Single implementation focus |
| Ambiguity check | ✅ Clear endpoint definitions |

---

## 9. Implementation Notes

- Use **full replacement** for schema updates (not merge)
- **Validate before save** to prevent invalid configs
- **Mock mode** for preview execution (no real LLM calls)
- **Error handling** returns detailed validation messages
- **Version tracking** in schema for history/rollback support