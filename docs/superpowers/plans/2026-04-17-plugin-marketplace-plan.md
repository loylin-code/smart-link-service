# Plugin Marketplace Implementation Plan

> **For agentic workers:** Execute task-by-task with TDD.

**Goal:** Implement Plugin Marketplace core features - models, API, loader

**Architecture:** Plugin/PluginInstallation models + REST API + Dynamic PluginLoader

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, pytest, asyncio

---

## Task 1: Plugin Data Models

**Files:**
- Create: `models/plugin.py`
- Modify: `models/__init__.py`

- [ ] **Step 1:** Create `models/plugin.py` with PluginStatus, Plugin, PluginInstallation

```python
# models/plugin.py
import enum
from sqlalchemy import Column, String, Text, JSON, DateTime, Integer, Boolean, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.session import Base
from models.application import generate_uuid

class PluginStatus(str, enum.Enum):
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"

class Plugin(Base):
    __tablename__ = "plugins"
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(20), nullable=False)
    author = Column(String(255), nullable=True)
    license = Column(String(50), nullable=True)
    tags = Column(JSON, default=list, nullable=False)
    icon = Column(String(500), nullable=True)
    package_name = Column(String(255), nullable=False)
    package_version = Column(String(20), nullable=False)
    entry_point = Column(String(255), nullable=False)
    status = Column(SQLEnum(PluginStatus), default=PluginStatus.PUBLISHED)
    install_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    installations = relationship("PluginInstallation", back_populates="plugin")
    __table_args__ = (Index('ix_plugins_name_status', 'name', 'status'),)

class PluginInstallation(Base):
    __tablename__ = "plugin_installations"
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=False)
    settings = Column(JSON, default=dict)
    enabled = Column(Boolean, default=True)
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    plugin = relationship("Plugin", back_populates="installations")
```

- [ ] **Step 2:** Add to `models/__init__.py` exports
- [ ] **Step 3:** Commit

---

## Task 2: Plugin Schemas

**Files:**
- Create: `schemas/plugin.py`

```python
# schemas/plugin.py
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

class PluginCreate(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    license: Optional[str] = "MIT"
    tags: List[str] = []
    package_name: str
    package_version: str
    entry_point: str

class PluginUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None

class PluginResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    version: str
    author: Optional[str] = None
    license: Optional[str] = None
    tags: List[str] = []
    status: str
    install_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

class PluginInstallRequest(BaseModel):
    settings: Dict[str, Any] = {}
    enabled: bool = True

class PluginInstallationResponse(BaseModel):
    id: str
    tenant_id: str
    plugin_id: str
    plugin_name: str
    enabled: bool
    installed_at: datetime
```

---

## Task 3: REST API Endpoints

**Files:**
- Create: `gateway/api/v1/plugins.py`
- Modify: `gateway/api/v1/__init__.py`

```python
# gateway/api/v1/plugins.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.session import get_db
from schemas.plugin import PluginCreate, PluginUpdate, PluginResponse, PluginInstallRequest, PluginInstallationResponse
from models.plugin import Plugin, PluginInstallation, PluginStatus
from typing import Optional, List

router = APIRouter(tags=["Plugins"])

@router.get("/")
async def list_plugins(
    search: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(20),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
) -> dict:
    query = select(Plugin).where(Plugin.status == PluginStatus.PUBLISHED)
    if search:
        query = query.where(Plugin.name.ilike(f"%{search}%"))
    if tag:
        query = query.where(Plugin.tags.contains([tag]))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    plugins = result.scalars().all()
    return {"data": [PluginResponse.model_validate(p) for p in plugins], "total": len(plugins)}

@router.post("/")
async def publish_plugin(
    request: PluginCreate,
    db: AsyncSession = Depends(get_db)
) -> dict:
    plugin = Plugin(**request.model_dump())
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)
    return {"data": PluginResponse.model_validate(plugin)}

@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(404, f"Plugin {plugin_id} not found")
    return {"data": PluginResponse.model_validate(plugin)}

@router.post("/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    request: PluginInstallRequest,
    tenant_id: str = "default",
    db: AsyncSession = Depends(get_db)
) -> dict:
    result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(404, f"Plugin {plugin_id} not found")
    installation = PluginInstallation(
        tenant_id=tenant_id,
        plugin_id=plugin_id,
        settings=request.settings,
        enabled=request.enabled
    )
    db.add(installation)
    plugin.install_count += 1
    await db.commit()
    await db.refresh(installation)
    return {"data": PluginInstallationResponse(
        id=installation.id,
        tenant_id=installation.tenant_id,
        plugin_id=installation.plugin_id,
        plugin_name=plugin.name,
        enabled=installation.enabled,
        installed_at=installation.installed_at
    )}

@router.delete("/{plugin_id}/uninstall")
async def uninstall_plugin(
    installation_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    result = await db.execute(select(PluginInstallation).where(PluginInstallation.id == installation_id))
    installation = result.scalar_one_or_none()
    if not installation:
        raise HTTPException(404, f"Installation {installation_id} not found")
    await db.delete(installation)
    await db.commit()
    return {"data": {"message": "Plugin uninstalled"}}
```

---

## Task 4: Plugin Loader

**Files:**
- Create: `agent/skills/loader.py`

```python
# agent/skills/loader.py
import importlib
from typing import Dict, Any, Optional
from agent.skills.base import BaseSkill
from core.exceptions import PluginLoadError

class PluginLoader:
    def __init__(self):
        self._loaded_plugins: Dict[str, BaseSkill] = {}
    
    async def load_plugin(self, plugin: Any, settings: Dict[str, Any]) -> BaseSkill:
        try:
            module = importlib.import_module(plugin.package_name)
            class_name = plugin.entry_point.split(":")[-1]
            skill_class = getattr(module, class_name)
            skill = skill_class(**settings)
            self._loaded_plugins[plugin.id] = skill
            return skill
        except Exception as e:
            raise PluginLoadError(
                f"Failed to load plugin {plugin.name}: {str(e)}",
                plugin_name=plugin.name,
                suggestions=["Check package is installed", "Verify entry_point format"]
            )
    
    async def unload_plugin(self, plugin_id: str) -> None:
        if plugin_id in self._loaded_plugins:
            del self._loaded_plugins[plugin_id]
    
    def get_loaded(self, plugin_id: str) -> Optional[BaseSkill]:
        return self._loaded_plugins.get(plugin_id)
```

---

## Task 5: PluginLoadError Exception

**Files:**
- Modify: `core/exceptions.py`

```python
class PluginLoadError(SmartLinkException):
    """Plugin loading error"""
    status_code = 500
    code = "PLUGIN_LOAD_ERROR"
    
    def __init__(self, message: str, plugin_name: Optional[str] = None, suggestions: Optional[List[str]] = None):
        details = {"plugin_name": plugin_name} if plugin_name else {}
        if suggestions:
            details["suggestions"] = suggestions
        self.suggestions = suggestions or []
        super().__init__(message, code=self.code, details=details)
```

---

## Task 6: Tests

**Files:**
- Create: `tests/unit/test_plugin_models.py`
- Create: `tests/unit/test_plugin_api.py`

---

## Verification

Run: `pytest tests/unit/test_plugin*.py -v`
Expected: All PASS