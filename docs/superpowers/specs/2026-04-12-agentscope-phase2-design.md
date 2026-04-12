# AgentScope Phase 2 Design - Pipeline & Memory Integration

**Date:** 2026-04-12
**Status:** Approved for Implementation
**Scope:** Pipeline (multi-agent orchestration) + Memory (session persistence)

---

## 1. Overview

Phase 2 extends Phase 1 AgentScope integration with:
- **Pipeline**: Multi-agent workflow orchestration using AgentScope `MsgHub`, `SequentialPipeline`, `FanoutPipeline`
- **Memory**: Session-based conversation persistence using AgentScope `AsyncSQLAlchemyMemory`

### Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Integration approach | Direct AgentScope API | Simpler architecture, tested components |
| Pipeline pattern | PlanAgent → SubAgent | Matches ARCHITECTURE-V2.md design |
| Memory scope | Short-term (session) | Context continuity within conversation |
| Success criteria | End-to-end demo | WebSocket streaming + frontend integration |

---

## 2. Pipeline Architecture

### 2.1 PlanAgent → SubAgent Pattern

```
User Request → Orchestrator → MsgHub (coordination)
                                │
                                ▼
                          PlanAgent (intent router)
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
               SubAgent1   SubAgent2   SubAgent3
               (Research)  (Code)      (Data)
                    │           │           │
                    └───────────┴───────────┘
                                │
                                ▼
                          Result Aggregation → Response
```

### 2.2 AgentScope Pipeline Components

| Component | API | Purpose |
|-----------|-----|---------|
| `MsgHub` | `agentscope.pipeline.MsgHub(participants, announcement, enable_auto_broadcast)` | Auto-broadcast messages to all participants |
| `SequentialPipeline` | `agentscope.pipeline.SequentialPipeline(agents)` | Chain agents: output of A → input of B |
| `FanoutPipeline` | `agentscope.pipeline.FanoutPipeline(agents, enable_gather=True)` | Parallel execution, gather results |
| `stream_printing_messages` | `agentscope.pipeline.stream_printing_messages(agents, coroutine_task)` | Convert agent output to async generator for streaming |

### 2.3 MsgHub Usage

```python
from agentscope.pipeline import MsgHub
from agentscope.message import Msg

async with MsgHub(
    participants=[plan_agent, research_agent, code_agent],
    announcement=Msg("user", "Please analyze this request", "user"),
) as hub:
    # Messages automatically broadcast to all participants
    await plan_agent()  # Routes to appropriate SubAgent
    await research_agent()  # Executes research
    await code_agent()  # Generates code if needed
```

### 2.4 Pipeline Execution Modes

**Sequential (A → B → C):**
```python
from agentscope.pipeline import SequentialPipeline

pipeline = SequentialPipeline(agents=[agent_a, agent_b, agent_c])
result = await pipeline(msg=input_msg)
# agent_a.output → agent_b.input → agent_c.input → final result
```

**Parallel (A, B, C → aggregation):**
```python
from agentscope.pipeline import FanoutPipeline

pipeline = FanoutPipeline(agents=[agent_a, agent_b, agent_c], enable_gather=True)
results = await pipeline(msg=input_msg)
# Returns list[Msg] from all agents
```

### 2.5 Implementation Files

| File | Status | Purpose |
|------|--------|---------|
| `agent/agentscope/hub.py` | Replace | Wrap AgentScope MsgHub with SmartLink config |
| `agent/agentscope/pipeline.py` | Create | Pipeline orchestration (Sequential, Parallel) |
| `agent/agentscope/agent_factory.py` | Extend | Add PlanAgent/SubAgent creation methods |
| `agent/core/orchestrator.py` | Extend | Add `execute_pipeline()` method |

---

## 3. Memory Integration

### 3.1 Short-term Memory (Session-based)

```
Conversation Session
    │
    ▼
AsyncSQLAlchemyMemory(user_id, session_id)
    │
    ├── add(Msg) → Store in SQLite/PostgreSQL
    ├── get_memory() → Retrieve conversation history
    ├── size() → Count messages
    └── clear() → End session cleanup
```

### 3.2 AgentScope Memory Components

| Component | API | Purpose |
|-----------|-----|---------|
| `MemoryBase` | Abstract base | Interface: `add()`, `get_memory()`, `clear()`, `delete()`, `size()` |
| `AsyncSQLAlchemyMemory` | `agentscope.memory.AsyncSQLAlchemyMemory(engine_or_session, user_id, session_id)` | SQLite/PostgreSQL-backed async memory |
| `RedisMemory` | `agentscope.memory.RedisMemory(host, port, user_id, session_id, key_ttl)` | Redis-backed memory with TTL |

### 3.3 Session Memory Adapter

```python
# agent/memory/agentscope_adapter.py
from agentscope.memory import AsyncSQLAlchemyMemory
from agentscope.message import Msg

class SessionMemory:
    """Wraps AsyncSQLAlchemyMemory for SmartLink sessions"""
    
    def __init__(self, db_session, user_id: str, session_id: str):
        self.memory = AsyncSQLAlchemyMemory(
            engine_or_session=db_session,
            user_id=user_id,
            session_id=session_id,
        )
    
    async def add_message(self, role: str, content: str, name: str = None):
        """Add message to session memory"""
        msg = Msg(name=name or role, content=content, role=role)
        await self.memory.add(msg)
    
    async def get_context(self) -> list[Msg]:
        """Retrieve conversation history"""
        return await self.memory.get_memory()
    
    async def get_message_count(self) -> int:
        """Count messages in session"""
        return await self.memory.size()
    
    async def clear_session(self):
        """Clear session memory on end"""
        await self.memory.clear()
```

### 3.4 Memory Scope Strategy

| Scope | Session ID | Use Case |
|-------|------------|----------|
| Per-conversation | `conv_{conversation_id}` | Current conversation context |
| Shared across Pipeline | Same session ID | Agents share conversation context |
| Per-agent isolation | `agent_{agent_id}_{conv_id}` | Agent-specific working memory (optional) |

### 3.5 Implementation Files

| File | Status | Purpose |
|------|--------|---------|
| `agent/memory/agentscope_adapter.py` | Create | Wrap AgentScope Memory for SmartLink |
| `agent/memory/manager.py` | Keep | Business logic, delegate to adapter |

---

## 4. API & Data Flow

### 4.1 WebSocket Flow

```
Client                          Server                          AgentScope
   │                               │                               │
   │ 1. WS Connect                 │                               │
   │──────────────────────────────►│                               │
   │                               │                               │
   │ 2. Chat message               │                               │
   │──────────────────────────────►│                               │
   │                               │                               │
   │                               │ 3. Load session memory        │
   │                               │──────────────────────────────►│ AsyncSQLAlchemyMemory
   │                               │                               │ .get_memory()
   │                               │                               │
   │                               │ 4. Create MsgHub              │
   │                               │──────────────────────────────►│ MsgHub(participants)
   │                               │                               │
   │                               │ 5. PlanAgent route intent     │
   │                               │──────────────────────────────►│ SequentialPipeline
   │                               │                               │ or FanoutPipeline
   │                               │                               │
   │                               │ 6. Stream response chunks     │
   │                               │◄──────────────────────────────│ stream_printing_messages
   │                               │                               │
   │ 7. Stream to client           │                               │
   │◄──────────────────────────────│                               │
   │                               │                               │
   │                               │ 8. Save to memory             │
   │                               │──────────────────────────────►│ memory.add(Msg)
```

### 4.2 Request Schema

```python
# schemas/common.py - Extended
from typing import Literal, Optional
from pydantic import BaseModel

class PipelineChatRequest(BaseModel):
    """Chat request with pipeline support"""
    message: str
    pipeline_type: Literal["single", "sequential", "parallel"] = "single"
    sub_agents: Optional[list[str]] = None  # Agent IDs for pipeline
    app_id: str
    conversation_id: Optional[str] = None
```

### 4.3 Response Schema

```python
# schemas/common.py - Extended
class StreamChunk(BaseModel):
    """Streamed response chunk"""
    type: Literal["token", "tool_call", "tool_result", "complete", "error"]
    data: dict
    agent_name: Optional[str] = None  # Which agent produced this chunk
    timestamp: int  # Milliseconds
```

### 4.4 API Endpoint Changes

| Endpoint | Current | Phase 2 Addition |
|----------|---------|-----------------|
| `/api/v1/chat/{client_id}` | Single agent | Add `pipeline_type` parameter |
| `/api/v1/agents/{agent_id}` | CRUD | Add `role` field (plan, sub, custom) |
| `/api/v1/conversations/{id}` | CRUD | Link to session memory |

---

## 5. Implementation Tasks

### 5.1 Pipeline Implementation

| Task | Files | Priority |
|------|-------|----------|
| Create `MsgHub` wrapper | `agent/agentscope/hub.py` | P0 |
| Create `PipelineManager` | `agent/agentscope/pipeline.py` | P0 |
| Add `create_plan_agent()` | `agent/agentscope/agent_factory.py` | P1 |
| Add `create_sub_agent()` | `agent/agentscope/agent_factory.py` | P1 |
| Extend `execute_pipeline()` | `agent/core/orchestrator.py` | P0 |

### 5.2 Memory Implementation

| Task | Files | Priority |
|------|-------|----------|
| Create `SessionMemory` adapter | `agent/memory/agentscope_adapter.py` | P0 |
| Integrate with WebSocket handler | `gateway/websocket/handlers.py` | P0 |
| Add memory to ReActAgent | `agent/agentscope/agent_factory.py` | P1 |

### 5.3 Test Implementation

| Task | Files | Priority |
|------|-------|----------|
| Pipeline unit tests | `tests/unit/test_pipeline.py` | P1 |
| Memory unit tests | `tests/unit/test_session_memory.py` | P1 |
| End-to-end demo test | `tests/integration/test_pipeline_flow.py` | P2 |

---

## 6. Dependencies

### 6.1 AgentScope Components Required

```python
# Already installed (Phase 1)
agentscope>=0.1.0

# Phase 2 imports
from agentscope.pipeline import MsgHub, SequentialPipeline, FanoutPipeline, stream_printing_messages
from agentscope.memory import AsyncSQLAlchemyMemory, MemoryBase
from agentscope.message import Msg
```

### 6.2 Database Schema

Existing schema supports `AsyncSQLAlchemyMemory`:
- `messages` table (already exists)
- `conversations` table (already exists)
- Add `session_id` field if needed for isolation

---

## 7. Success Criteria

### 7.1 End-to-End Demo Requirements

| Requirement | Verification |
|-------------|--------------|
| WebSocket connects | `scripts/test_websocket.py` passes |
| Multi-agent pipeline executes | Pipeline test passes |
| Session memory persists | Conversation history retrievable after disconnect |
| Streaming output works | Chunks received in order |
| Frontend can display | Frontend project demo successful |

### 7.2 Test Coverage

- Unit tests for Pipeline components (MsgHub, SequentialPipeline)
- Unit tests for SessionMemory adapter
- Integration test for PlanAgent → SubAgent flow
- WebSocket streaming test

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| AgentScope API changes | Pin version, use stable APIs only |
| Memory performance with large history | Add pagination, summarize old messages |
| Pipeline complexity | Start with single-agent, incrementally add pipeline modes |
| WebSocket connection issues | Use existing heartbeat manager, retry logic |

---

## 9. References

- AgentScope Pipeline Tutorial: https://doc.agentscope.io/tutorial/task_pipeline.html
- AgentScope Memory Tutorial: https://doc.agentscope.io/tutorial/task_memory.html
- SmartLink ARCHITECTURE-V2.md: Phase 2 Pipeline/Memory design (lines 1818-2007)