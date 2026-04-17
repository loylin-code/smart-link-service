# Plugin Marketplace Design

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Core Plugin Marketplace - Data Model + REST API + Dynamic Loader
**Related:** Phase 4: 智能化 (ARCHITECTURE-V2.md)

---

## 1. Overview

为 SmartLink 添加 Skill/Plugin Marketplace，支持：
- 插件发布（开发者上传）
- 插件发现（搜索、分类）
- 插件安装（动态加载）
- 插件版本管理

**Phase 2 后续功能（本次不实现）**:
- 插件评分/统计
- Sandbox 执行隔离
- 插件依赖声明

---

## 2. Data Models

### 2.1 Plugin Model

```python
# models/plugin.py

class PluginStatus(str, enum.Enum):
    """Plugin status enum"""
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    ARCHIVED = "archived"


class Plugin(Base):
    """Plugin marketplace model"""
    __tablename__ = "plugins"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)  # Owner
    
    # Plugin metadata
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(20), nullable=False)
    author = Column(String(255), nullable=True)
    license = Column(String(50), nullable=True)
    tags = Column(JSON, default=list, nullable=False)  # ["search", "data"]
    icon = Column(String(500), nullable=True)  # URL
    
    # Plugin package
    package_name = Column(String(255), nullable=False)  # pip package name
    package_version = Column(String(20), nullable=False)
    entry_point = Column(String(255), nullable=False)  # "my_plugin:MySkill"
    
    # Status
    status = Column(SQLEnum(PluginStatus), default=PluginStatus.PUBLISHED)
    
    # Statistics (Phase 2)
    install_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    installations = relationship("PluginInstallation", back_populates="plugin")
```

### 2.2 PluginInstallation Model

```python
class PluginInstallation(Base):
    """Plugin installation record"""
    __tablename__ = "plugin_installations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    plugin_id = Column(String, ForeignKey("plugins.id"), nullable=False)
    
    # Installation settings
    settings = Column(JSON, default=dict)  # Plugin-specific config
    enabled = Column(Boolean, default=True)
    
    # Timestamps
    installed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    plugin = relationship("Plugin", back_populates="installations")
```

---

## 3. REST API

### 3.1 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/plugins/` | List plugins (search/filter) |
| POST | `/api/v1/plugins/` | Publish new plugin |
| GET | `/api/v1/plugins/{id}` | Get plugin details |
| PUT | `/api/v1/plugins/{id}` | Update plugin metadata |
| DELETE | `/api/v1/plugins/{id}` | Unpublish plugin |
| POST | `/api/v1/plugins/{id}/install` | Install to tenant |
| DELETE | `/api/v1/plugins/{id}/uninstall` | Remove from tenant |
| GET | `/api/v1/plugins/installed` | List tenant's installed plugins |

### 3.2 Schemas

```python
# schemas/plugin.py

class PluginCreate(BaseModel):
    """Publish plugin request"""
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    license: Optional[str] = "MIT"
    tags: List[str] = []
    package_name: str
    package_version: str
    entry_point: str


class PluginResponse(BaseModel):
    """Plugin response"""
    id: str
    name: str
    description: Optional[str]
    version: str
    author: Optional[str]
    license: Optional[str]
    tags: List[str]
    status: str
    install_count: int
    created_at: datetime


class PluginInstallRequest(BaseModel):
    """Install plugin request"""
    settings: Dict[str, Any] = {}
    enabled: bool = True
```

---

## 4. Plugin Loader

### 4.1 Dynamic Loading

```python
# agent/skills/loader.py

class PluginLoader:
    """Dynamic plugin loader"""
    
    def __init__(self):
        self._loaded_plugins: Dict[str, BaseSkill] = {}
    
    async def load_plugin(self, installation: PluginInstallation) -> BaseSkill:
        """Load plugin from installation
        
        Args:
            installation: PluginInstallation record
            
        Returns:
            Loaded Skill instance
            
        Raises:
            PluginLoadError if loading fails
        """
        plugin = installation.plugin
        
        try:
            # Import module
            module = importlib.import_module(plugin.package_name)
            
            # Get entry point
            skill_class = getattr(module, plugin.entry_point.split(":")[1])
            
            # Instantiate with settings
            skill = skill_class(**installation.settings)
            
            self._loaded_plugins[installation.id] = skill
            return skill
            
        except Exception as e:
            raise PluginLoadError(
                f"Failed to load plugin {plugin.name}",
                plugin_name=plugin.name,
                suggestions=["Check package is installed", "Verify entry point"]
            )
    
    async def unload_plugin(self, installation_id: str) -> None:
        """Unload plugin"""
        if installation_id in self._loaded_plugins:
            del self._loaded_plugins[installation_id]
    
    def get_loaded_skill(self, installation_id: str) -> Optional[BaseSkill]:
        """Get loaded skill"""
        return self._loaded_plugins.get(installation_id)
```

### 4.2 Skill Registry Enhancement

```python
# agent/skills/base.py (modify SkillRegistry)

class SkillRegistry:
    """Enhanced skill registry with plugin support"""
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._plugin_loader = PluginLoader()
        self._auto_discover()
    
    async def register_plugin_skill(
        self,
        installation: PluginInstallation
    ) -> None:
        """Register plugin skill"""
        skill = await self._plugin_loader.load_plugin(installation)
        self.register(skill)
    
    async def unregister_plugin_skill(
        self,
        installation_id: str,
        skill_name: str
    ) -> None:
        """Unregister plugin skill"""
        await self._plugin_loader.unload_plugin(installation_id)
        if skill_name in self._skills:
            del self._skills[skill_name]
```

---

## 5. Implementation Tasks

| Task | Files | Description |
|------|-------|-------------|
| Task 1 | `models/plugin.py` | Plugin + PluginInstallation models |
| Task 2 | `schemas/plugin.py` | Request/Response schemas |
| Task 3 | `gateway/api/v1/plugins.py` | REST API endpoints |
| Task 4 | `agent/skills/loader.py` | PluginLoader class |
| Task 5 | `agent/skills/base.py` | SkillRegistry enhancement |
| Task 6 | Tests | Unit tests for models and API |

---

## 6. Success Criteria

- [ ] Plugin/PluginInstallation models created
- [ ] REST API endpoints functional
- [ ] PluginLoader can dynamically load skills
- [ ] SkillRegistry integrates with PluginLoader
- [ ] All tests pass

---

**Document Status:** Approved
**Next Step:** Invoke writing-plans skill to create implementation plan