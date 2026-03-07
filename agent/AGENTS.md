# AGENT RUNTIME

## OVERVIEW

Core execution engine with hybrid workflow/chat modes, skill auto-discovery, and LiteLLM multi-provider support.

## STRUCTURE

```
agent/
├── core/
│   ├── orchestrator.py   # Main execution engine
│   └── context.py        # State, messages, tool results
├── llm/
│   └── client.py         # LiteLLM wrapper, streaming
└── skills/
    ├── base.py           # BaseSkill, SkillRegistry
    └── builtin/          # Auto-discovered skills
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add skill | `skills/builtin/*.py` | Inherit `BaseSkill`, auto-registered |
| Change LLM provider | `llm/client.py:28-29` | Provider/model defaults |
| Workflow execution | `core/orchestrator.py:227-243` | Node-by-node, sequential |
| Chat execution | `core/orchestrator.py:270-287` | Tool calling loop |
| Context state | `core/context.py` | Messages, variables, results |

## CONVENTIONS

- **Skill auto-discovery**: `SkillRegistry` scans `skills/builtin/` on init. Any `BaseSkill` subclass with a `name` attribute gets instantiated and registered automatically.
- **Two execution modes**: 
  - **Workflow mode**: If `schema.nodes` exists, executes nodes sequentially via `_execute_node()`
  - **Chat mode**: Simple LLM + tool calling loop
- **Node types**: `llm`, `skill`, `tool` - each handled in `_execute_node()`
- **Tool format**: Skills expose `to_openai_tool()` for function calling compatibility
- **Streaming**: `execute_stream()` yields chunks; `execute()` returns complete result

## ANTI-PATTERNS

### Unimplemented

| Feature | Location | Status |
|---------|----------|--------|
| Parallel workflow execution | `orchestrator.py:238` | Sequential only, TODO |
| MCP tool execution | `orchestrator.py:319` | Empty placeholder |
| Sophisticated templating | `orchestrator.py:390` | Simple `{var}` substitution |
| Skill param validation | `skills/base.py:60` | Returns True, no schema check |
