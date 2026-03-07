# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-05
**Commit:** cdb69c0
**Branch:** main

## OVERVIEW

SmartLink Agent Management Platform backend - FastAPI service with three-layer architecture (Gateway → Services → Agent Runtime). Supports multi-LLM via LiteLLM, WebSocket streaming, and plugin-based Skill system.

## STRUCTURE

```
smart-link-service/
├── gateway/          # API layer: REST routes, WebSocket, middleware
├── services/         # Business logic: app, resource, conversation services
├── agent/            # Runtime: orchestrator, LLM client, skills registry
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic request/response schemas
├── core/             # Config, security, exceptions
├── db/               # Database session management
├── docker/           # Dockerfile, docker-compose, startup scripts
└── scripts/          # Utility scripts (init_db.py)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add API endpoint | `gateway/api/v1/` | Register in `gateway/api/v1/__init__.py` |
| Add WebSocket handler | `gateway/websocket/handlers.py` | |
| Add business logic | `services/` | Follow service pattern |
| Add Skill plugin | `agent/skills/builtin/` | Auto-discovered on startup |
| Configure LLM | `agent/llm/client.py` | Uses LiteLLM |
| Database models | `models/application.py` | SQLAlchemy async |
| Request schemas | `schemas/common.py` | Pydantic v2 |
| Config settings | `core/config.py` | Environment-based |
| Auth middleware | `gateway/middleware/auth.py` | API Key validation |

## CONVENTIONS

- **Line length:** 100 chars (Black default is 88)
- **Import order:** isort with `profile="black"`, `multi_line_output=3`
- **Types:** Strict - `disallow_untyped_defs=true` in mypy
- **Async:** All database operations use async SQLAlchemy
- **Tests:** pytest with `asyncio_mode="auto"` (no tests written yet)

## ANTI-PATTERNS

### Security (MUST FIX before production)

| Pattern | Location | Action |
|---------|----------|--------|
| Default API key | `.env.example`, `docker-compose.yml` | Change `MASTER_API_KEY` and `SECRET_KEY` |
| Master-key-only auth | `core/security.py:31-38` | Implement database API key lookup |

### Unimplemented Features

| Feature | Location | Status |
|---------|----------|--------|
| Skill schema validation | `agent/skills/base.py:60` | TODO |
| Web search skill | `agent/skills/builtin/search.py:40` | Returns mock data |
| Data analysis skill | `agent/skills/builtin/search.py:106` | Returns mock data |
| Parallel workflow execution | `agent/core/orchestrator.py:238` | Sequential only |
| MCP tool execution | `agent/core/orchestrator.py:319` | Empty placeholder |

## UNIQUE STYLES

- **Flat module structure:** No `app/` package - `gateway/`, `agent/`, `services/` are siblings
- **Auto-discovery:** Skills in `agent/skills/builtin/` auto-register on import
- **Hybrid execution:** Both structured workflow (nodes/edges) and simple chat modes
- **Entry point:** `gateway/main.py` (not at root) - imports as `from gateway.main import app`

## COMMANDS

```bash
# Install (dev)
pip install -e ".[dev]"

# Run development server
uvicorn gateway.main:app --reload

# Run via Docker Compose
cd docker && docker-compose up -d

# Initialize database
python scripts/init_db.py

# Run tests (when added)
pytest --cov=. tests/

# Format code
black . --line-length 100
isort . --line-length 100 --profile black

# Type check
mypy .
```

## NOTES

- **No tests exist** - `tests/` directory missing, pytest configured
- **No Alembic migrations** - Uses `scripts/init_db.py` for schema init
- **`smart_link_service/` is empty** - Stub package, not used
- **No CI/CD** - GitHub Actions not configured
- **Redis pub/sub placeholder** - Horizontal scaling not implemented