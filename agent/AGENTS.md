# AGENT RUNTIME

## OVERVIEW

AgentScope-based execution engine with MessageHub coordination, ReActAgent execution, and Toolkit integration. Supports skill auto-discovery and LiteLLM multi-provider support.

## STRUCTURE

```
agent/
├── agentscope/           # AgentScope Integration
│   ├── hub.py            # MsgHub wrapper (Phase 2)
│   ├── pipeline.py       # PipelineManager (Phase 2)
│   ├── agent_factory.py  # ReActAgent creation + memory + sub/plan agents
│   └── toolkit.py        # Skill/MCP registration
├── memory/               # Memory System (Phase 2)
│   ├── agentscope_adapter.py  # SessionMemory wrapper
│   └── manager.py        # Memory management
├── core/
│   ├── orchestrator.py   # Main execution engine + pipeline execution
│   └── context.py        # State, messages, tool results
├── llm/
│   └── client.py         # LiteLLM wrapper, streaming
├── skills/
│   ├── base.py           # BaseSkill, SkillRegistry
│   └── builtin/          # Auto-discovered skills
└── mcp/
    └── client.py         # MCP protocol client
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Create agent | `agentscope/agent_factory.py` | `AgentFactory.create_agent()` |
| Create agent with memory | `agentscope/agent_factory.py` | `create_agent_with_memory()` |
| Create SubAgent | `agentscope/agent_factory.py` | `create_sub_agent()` |
| Create PlanAgent | `agentscope/agent_factory.py` | `create_plan_agent()` |
| Register skill | `agentscope/toolkit.py` | `AgentToolkit.register_skill()` |
| Message coordination | `agentscope/hub.py` | `AgentHub` (MsgHub wrapper) |
| Pipeline execution | `agentscope/pipeline.py` | `PipelineManager.execute()` |
| Session memory | `memory/agentscope_adapter.py` | `SessionMemory` |
| Execute agent | `core/orchestrator.py` | `AgentOrchestrator.execute()` |
| Execute pipeline | `core/orchestrator.py` | `execute_pipeline()` |
| Stream execution | `core/orchestrator.py` | `execute_stream()` yields chunks |
| Load agent config | `core/orchestrator.py` | `_load_agent_config()` from DB |
| Context state | `core/context.py` | Messages, variables, results |

## ARCHITECTURE

### Execution Flow

```
User Request → Orchestrator → AgentFactory → ReActAgent → Toolkit → LLM/Skills → Response
```

### Core Components

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| `AgentHub` | MsgHub wrapper for message coordination | `get_instance()`, `initialize_with_msghub()`, `broadcast()` |
| `PipelineManager` | Multi-agent workflow execution | `execute()`, `execute_stream()` (SINGLE/SEQUENTIAL/PARALLEL) |
| `SessionMemory` | Session-based conversation memory | `add_message()`, `get_context()`, `clear_session()` |
| `AgentFactory` | Agent creation | `create_agent()`, `create_agent_with_memory()`, `create_sub_agent()`, `create_plan_agent()` |
| `AgentToolkit` | Tool registration | `register_skill()`, `register_mcp_server()`, `get_tool_schemas()` |
| `AgentOrchestrator` | Execution engine | `execute()`, `execute_stream()`, `execute_pipeline()`, `_load_agent_config()` |

## CONVENTIONS

- **AgentScope Integration**: Uses `MessageHub`, `ReActAgent`, `Toolkit` from AgentScope framework
- **Skill auto-discovery**: `SkillRegistry` scans `skills/builtin/` on init. Skills registered via `AgentToolkit.register_skill()`
- **Agent-centric execution**: `execute(agent_id, input_data)` - loads Agent Role from database
- **Streaming**: `execute_stream()` yields typed chunks (`chunk`, `complete`, `error`)
- **Tool format**: Skills wrapped as Toolkit functions for ReActAgent tool calling
- **MCP support**: MCP servers registered via `AgentToolkit.register_mcp_server()`

## API

### AgentOrchestrator

```python
from agent.core.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()

# Execute agent
result = await orchestrator.execute(
    agent_id="agent-001",
    input_data={"message": "Hello"}
)

# Stream execution
async for chunk in orchestrator.execute_stream(agent_id, input_data):
    print(chunk["content"])
```

### AgentFactory

```python
from agent.agentscope.agent_factory import AgentFactory

factory = AgentFactory()

# Create agent
agent = await factory.create_agent(
    name="assistant",
    sys_prompt="You are a helpful assistant",
    toolkit=toolkit
)

# Create from role config
agent = await factory.create_sub_agent(role_config, toolkit)
```

### AgentToolkit

```python
from agent.agentscope.toolkit import AgentToolkit

toolkit = AgentToolkit()

# Register skill
await toolkit.register_skill(skill_instance)

# Register MCP
await toolkit.register_mcp_server(mcp_client)

# Get schemas for tool calling
schemas = toolkit.get_tool_schemas()
```

## DEPENDENCIES

- `agentscope>=0.1.0` - Agent framework (PyPI)
- `litellm>=1.20.0` - Multi-provider LLM
- `mcp>=0.9.0` - Model Context Protocol

## MIGRATION NOTES

### Removed (v2.0)

| Component | Replacement |
|-----------|-------------|
| `executor.py` (WorkflowExecutor) | AgentScope Pipeline (Phase 2) |
| `loop.py` (AgentLoop) | ReActAgent built-in loop |

### Changed

| Old API | New API |
|---------|---------|
| `execute(app_id, ...)` | `execute(agent_id, ...)` |
| `_execute_node()` | ReActAgent handles execution |
| `WorkflowExecutor` | AgentToolkit + ReActAgent |