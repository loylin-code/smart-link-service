# SERVICES LAYER

## OVERVIEW

Business logic for Application, Resource, and Conversation management. Pure async services with no HTTP concerns.

## WHERE TO LOOK

| Task | File |
|------|------|
| Application CRUD | `application_service.py` |
| Run app validation | `application_service.py:161` |
| Conversation management | `conversation_service.py` |
| Message history | `conversation_service.py:77` |
| Skill/MCP CRUD | `resource_service.py` |

## CONVENTIONS

### Service Pattern

```python
class ServiceName:
    def __init__(self, db: AsyncSession):
        self.db = db
```

- Constructor takes `db: AsyncSession`
- All methods are `async`
- Return `Optional[T]` for single record lookups
- Return `Tuple[List[T], int]` for paginated lists

### Status Validation

Application must be `PUBLISHED` before running (line 161-162). Returns `ValidationError` if not.

### Id Generation

```python
f"{prefix}_{uuid.uuid4().hex[:12]}"  # app_xxx, skill_xxx, mcp_xxx
```

### Transaction Pattern

Always commit in this order: `add()` → `commit()` → `refresh()` → return.
