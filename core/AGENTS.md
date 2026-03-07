# CORE MODULE

Infrastructure layer for configuration, security, and exceptions.

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add config setting | `config.py` | Add field to `Settings` class, restart to pick up |
| Update auth logic | `security.py` | `verify_api_key()` needs database lookup for production |
| Add exception type | `exceptions.py` | Inherit from `SmartLinkException`, add domain-specific code |
| Import settings | `__init__.py` | `from core import settings` anywhere in the app |

## CONVENTIONS

- **Settings pattern:** Single `Settings` class using Pydantic v2 `BaseSettings`
- **Global instance:** Import `settings` from `core` (not `core.config`)
- **Required env vars:** `DATABASE_URL`, `REDIS_URL`, `MASTER_API_KEY`, `SECRET_KEY`
- **Exception design:** All exceptions extend `SmartLinkException` with `message`, `code`, and optional `details`
- **Security helpers:** `verify_password`, `generate_api_key`, JWT token functions in `security.py`

## ANTI-PATTERNS

### Security

| Pattern | Location | Action |
|---------|----------|--------|
| Master-key-only auth | `security.py:31-38` | Implement database API key lookup before production |

### Configuration

| Pattern | Issue |
|---------|-------|
| Accessing `os.environ` directly | Use `settings.FIELD_NAME` instead |
| Creating multiple Settings instances | Always import the global `settings` object |
