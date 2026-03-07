# Gateway Layer

API Gateway for SmartLink - FastAPI application with REST endpoints, WebSocket support, and middleware stack.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add REST endpoint | `gateway/api/v1/` | Register in `gateway/api/v1/__init__.py` |
| Add WebSocket handler | `gateway/websocket/handlers.py` | Import in `websocket.py` route |
| Modify auth logic | `gateway/middleware/auth.py` | `PUBLIC_PATHS` for exclusions |
| WebSocket connection | `gateway/websocket/manager.py` | Singleton `manager` instance |
| App factory/lifespan | `gateway/main.py` | Startup/shutdown hooks |

## KEY PATTERNS

**Entry Point**: `gateway.main:app` - FastAPI instance created here with lifespan manager.

**Middleware Stack** (applied in order):
1. `CORSMiddleware` - CORS handling (first)
2. `LoggingMiddleware` - Request/response logging with timing
3. `APIKeyMiddleware` - API key validation (skips `/ws*` paths)

**Authentication Flow**:
- REST: `X-API-Key` header validated by `APIKeyMiddleware`
- WebSocket: `api_key` query param or header via `verify_api_key_ws()`
- Public paths (no auth): `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`, `/metrics`, `/static*`, `/ws*`

**WebSocket Flow**:
1. Client connects to `/ws/chat/{client_id}?app_id=xxx&api_key=xxx`
2. `verify_api_key_ws()` validates credentials
3. `manager.connect()` registers connection
4. Message loop dispatches to handlers (`handle_chat_message`, `handle_ping`)
5. `manager.disconnect()` on close

**Router Registration**: All v1 routes mounted in `gateway/api/v1/__init__.py` with prefixes.

## ANTI-PATTERNS

- Don't add auth bypass paths without updating `PUBLIC_PATHS` in auth middleware
- WebSocket handlers receive database session from context manager in route, don't create new ones
- Redis pub/sub in `manager.py` is placeholder - not implemented for multi-instance scaling yet
