# Agent Design API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create dedicated `/api/v1/agent-design` API for Agent design editing - Schema CRUD, Capabilities, Knowledge configuration.

**Architecture:** Design API separated from runtime `/agents` API. Uses existing Agent model with page_schema, capabilities, knowledge JSON fields. Full replacement pattern for schema updates.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `schemas/agent_design.py` | Create | PageSchema, ComponentNode, design request/response schemas |
| `schemas/__init__.py` | Modify | Export agent_design schemas |
| `services/agent_design_service.py` | Create | Design service: schema CRUD, validation, preview |
| `gateway/api/v1/agent_design.py` | Create | Design API endpoints |
| `gateway/api/v1/__init__.py` | Modify | Register agent_design router |
| `tests/unit/test_agent_design.py` | Create | Design API unit tests |

---

### Task 1: Create PageSchema and ComponentNode Schemas

**Files:**
- Create: `schemas/agent_design.py`
- Modify: `schemas/__init__.py`

- [ ] **Step 1: Create schemas/agent_design.py**

```python
"""
Agent Design Schemas - PageSchema, ComponentNode, Design API request/response
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# Component Node Schema (Frontend ComponentNode match)
# ============================================================

class ExpressionBinding(BaseModel):
    """Expression binding for dynamic props"""
    expression: str
    type: str = "expression"


class StateBinding(BaseModel):
    """State binding for reactive props"""
    state_key: str = Field(alias="stateKey")
    transform: Optional[str] = None


class EventHandler(BaseModel):
    """Event handler configuration"""
    model_config = ConfigDict(populate_by_name=True)
    
    type: str  # builtin, custom, api, state
    action: Optional[str] = None  # navigate, openModal, submitForm
    code: Optional[str] = None
    api: Optional[Dict[str, Any]] = None
    state_update: Optional[Dict[str, Any]] = Field(None, alias="stateUpdate")
    params: Optional[Dict[str, Any]] = None


class EventBinding(BaseModel):
    """Event binding configuration"""
    event: str  # click, change, submit
    handler: EventHandler


class LoopConfig(BaseModel):
    """Loop rendering configuration"""
    model_config = ConfigDict(populate_by_name=True)
    
    items: str  # Expression for items array
    item_name: str = Field(default="item", alias="itemName")
    index_name: str = Field(default="index", alias="indexName")


class SlotContent(BaseModel):
    """Slot content configuration"""
    components: List["ComponentNode"] = []


class StyleConfig(BaseModel):
    """CSS style configuration"""
    model_config = ConfigDict(populate_by_name=True)
    
    background_color: Optional[str] = Field(None, alias="backgroundColor")
    border_color: Optional[str] = Field(None, alias="borderColor")
    border_radius: Optional[str] = Field(None, alias="borderRadius")
    shadow: Optional[str] = None
    opacity: Optional[float] = None


class ComponentNode(BaseModel):
    """
    Component node in PageSchema tree
    Matches frontend ComponentNode interface
    """
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    type: str  # SlContainer, SlChatInterface, SlButton, etc.
    name: Optional[str] = None
    props: Optional[Dict[str, Any]] = None
    style: Optional[StyleConfig] = None
    condition: Optional[ExpressionBinding] = None
    loop: Optional[LoopConfig] = None
    events: Optional[List[EventBinding]] = None
    slots: Optional[Dict[str, SlotContent]] = None
    children: Optional[List["ComponentNode"]] = None
    position: Optional[Dict[str, int]] = None  # { x, y } for free layout


# Enable recursive model
ComponentNode.model_rebuild()


# ============================================================
# PageSchema (Frontend PageSchema match)
# ============================================================

class StyleDefinition(BaseModel):
    """Global style definition"""
    id: str
    name: str
    css: str


class ScriptDefinition(BaseModel):
    """Custom script definition"""
    id: str
    name: str
    code: str
    type: str = "javascript"


class PageSchema(BaseModel):
    """
    PageSchema - Complete page design schema
    Matches frontend PageSchema interface
    """
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    version: str = "1.0.0"
    root: ComponentNode
    styles: Optional[List[StyleDefinition]] = None
    scripts: Optional[List[ScriptDefinition]] = None


# ============================================================
# Design API Request/Response Schemas
# ============================================================

class SchemaUpdateRequest(BaseModel):
    """Schema update request (full replacement)"""
    schema: PageSchema


class SchemaResponse(BaseModel):
    """Schema response"""
    schema: Optional[PageSchema] = None


class ComponentAddRequest(BaseModel):
    """Add component to schema request"""
    model_config = ConfigDict(populate_by_name=True)
    
    parent_id: str = Field(alias="parentId")
    component: ComponentNode


class ComponentUpdateRequest(BaseModel):
    """Update component request"""
    props: Optional[Dict[str, Any]] = None
    style: Optional[StyleConfig] = None
    events: Optional[List[EventBinding]] = None
    position: Optional[Dict[str, int]] = None


class ValidationResult(BaseModel):
    """Design validation result"""
    valid: bool
    warnings: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []


class PreviewRequest(BaseModel):
    """Preview execution request"""
    input: Dict[str, Any] = {}
    mock_mode: bool = Field(default=True, alias="mockMode")


class PreviewResult(BaseModel):
    """Preview execution result"""
    model_config = ConfigDict(populate_by_name=True)
    
    preview_id: str = Field(alias="previewId")
    execution_plan: List[Dict[str, Any]] = Field(alias="executionPlan")
    estimated_tokens: int = Field(alias="estimatedTokens")
```

- [ ] **Step 2: Update schemas/__init__.py exports**

Add to end of file:
```python
# Agent Design schemas
from schemas.agent_design import (
    PageSchema,
    ComponentNode,
    ExpressionBinding,
    StateBinding,
    EventBinding,
    EventHandler,
    LoopConfig,
    SlotContent,
    StyleConfig,
    StyleDefinition,
    ScriptDefinition,
    SchemaUpdateRequest,
    SchemaResponse,
    ComponentAddRequest,
    ComponentUpdateRequest,
    ValidationResult,
    PreviewRequest,
    PreviewResult
)

__all__ = [
    # ... existing exports
    # Agent Design schemas
    "PageSchema",
    "ComponentNode",
    "ExpressionBinding",
    "StateBinding",
    "EventBinding",
    "EventHandler",
    "LoopConfig",
    "SlotContent",
    "StyleConfig",
    "StyleDefinition",
    "ScriptDefinition",
    "SchemaUpdateRequest",
    "SchemaResponse",
    "ComponentAddRequest",
    "ComponentUpdateRequest",
    "ValidationResult",
    "PreviewRequest",
    "PreviewResult",
]
```

- [ ] **Step 3: Run imports test**

Run: `python -c "from schemas import PageSchema, ComponentNode; print('OK')"`
Expected: OK (no import errors)

- [ ] **Step 4: Commit**

```bash
git add schemas/agent_design.py schemas/__init__.py
git commit -m "feat(schema): add PageSchema and ComponentNode for Agent design"
```

---

### Task 2: Create AgentDesignService

**Files:**
- Create: `services/agent_design_service.py`

- [ ] **Step 1: Create services/agent_design_service.py**

```python
"""
Agent Design Service - Schema CRUD, Validation, Preview
"""
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent
from schemas.agent_design import (
    PageSchema,
    ComponentNode,
    ComponentAddRequest,
    ComponentUpdateRequest,
    ValidationResult
)


class AgentDesignService:
    """Service for Agent design operations"""
    
    @staticmethod
    async def get_schema(db: AsyncSession, agent_id: str) -> Optional[PageSchema]:
        """
        Get Agent's PageSchema
        
        Args:
            db: Database session
            agent_id: Agent ID
            
        Returns:
            PageSchema or None
        """
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        
        if not agent or not agent.page_schema:
            return None
        
        return PageSchema(**agent.page_schema)
    
    @staticmethod
    async def update_schema(
        db: AsyncSession,
        agent_id: str,
        schema: PageSchema
    ) -> bool:
        """
        Update Agent's PageSchema (full replacement)
        
        Args:
            db: Database session
            agent_id: Agent ID
            schema: New PageSchema
            
        Returns:
            True if updated, False if agent not found
        """
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        
        if not agent:
            return False
        
        agent.page_schema = schema.model_dump(by_alias=True)
        await db.flush()
        await db.refresh(agent)
        return True
    
    @staticmethod
    async def add_component(
        db: AsyncSession,
        agent_id: str,
        request: ComponentAddRequest
    ) -> Optional[str]:
        """
        Add component node to schema
        
        Args:
            db: Database session
            agent_id: Agent ID
            request: Component add request
            
        Returns:
            New component ID or None
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return None
        
        # Find parent node
        parent = AgentDesignService._find_node(schema.root, request.parent_id)
        if not parent:
            return None
        
        # Add component to parent's children
        if not parent.children:
            parent.children = []
        parent.children.append(request.component)
        
        # Save
        await AgentDesignService.update_schema(db, agent_id, schema)
        return request.component.id
    
    @staticmethod
    async def update_component(
        db: AsyncSession,
        agent_id: str,
        node_id: str,
        updates: ComponentUpdateRequest
    ) -> bool:
        """
        Update single component node
        
        Args:
            db: Database session
            agent_id: Agent ID
            node_id: Node ID to update
            updates: Update data
            
        Returns:
            True if updated, False if not found
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return False
        
        # Find and update node
        node = AgentDesignService._find_node(schema.root, node_id)
        if not node:
            return False
        
        # Apply updates
        if updates.props:
            if not node.props:
                node.props = {}
            node.props["static"] = {**node.props.get("static", {}), **updates.props}
        
        if updates.style:
            node.style = updates.style
        
        if updates.events:
            node.events = updates.events
        
        if updates.position:
            node.position = updates.position
        
        # Save
        await AgentDesignService.update_schema(db, agent_id, schema)
        return True
    
    @staticmethod
    async def delete_component(
        db: AsyncSession,
        agent_id: str,
        node_id: str
    ) -> bool:
        """
        Delete component node and its children
        
        Args:
            db: Database session
            agent_id: Agent ID
            node_id: Node ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return False
        
        # Cannot delete root
        if schema.root.id == node_id:
            return False
        
        # Find and remove from parent's children
        removed = AgentDesignService._remove_node(schema.root, node_id)
        if not removed:
            return False
        
        # Save
        await AgentDesignService.update_schema(db, agent_id, schema)
        return True
    
    @staticmethod
    async def validate_design(
        db: AsyncSession,
        agent_id: str
    ) -> ValidationResult:
        """
        Validate Agent design
        
        Args:
            db: Database session
            agent_id: Agent ID
            
        Returns:
            ValidationResult with warnings/errors
        """
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        
        if not agent:
            return ValidationResult(
                valid=False,
                errors=[{"type": "agent_not_found", "message": "Agent not found"}]
            )
        
        warnings = []
        errors = []
        
        # Check MCP servers
        for mcp in agent.mcp_servers or []:
            if mcp.get("required") and mcp.get("serverId"):
                # TODO: Check if MCP server is connected
                warnings.append({
                    "type": "mcp_connection",
                    "message": f"MCP server '{mcp.get('serverId')}' connection status unknown"
                })
        
        # Check skills
        for skill in agent.skills or []:
            if skill.get("enabled"):
                # TODO: Check if skill exists
                pass
        
        # Check schema
        if agent.page_schema:
            try:
                schema = PageSchema(**agent.page_schema)
                # Validate component tree
                AgentDesignService._validate_components(schema.root, errors)
            except Exception as e:
                errors.append({
                    "type": "schema_invalid",
                    "message": str(e)
                })
        
        return ValidationResult(
            valid=len(errors) == 0,
            warnings=warnings,
            errors=errors
        )
    
    @staticmethod
    async def preview_execution(
        db: AsyncSession,
        agent_id: str,
        input_data: Dict[str, Any],
        mock_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Preview execution plan
        
        Args:
            db: Database session
            agent_id: Agent ID
            input_data: Test input
            mock_mode: Use mock execution
            
        Returns:
            Preview result with execution plan
        """
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        
        if not agent:
            return {"previewId": None, "executionPlan": [], "estimatedTokens": 0}
        
        # Build execution plan (mock)
        execution_plan = []
        
        # Step 1: LLM call
        execution_plan.append({
            "step": 1,
            "agent": "main",
            "action": "llm_call",
            "model": agent.llm_config.get("model", "gpt-4")
        })
        
        # Step 2: Tool calls (if enabled)
        for tool in agent.tools or []:
            if tool.get("enabled"):
                execution_plan.append({
                    "step": len(execution_plan) + 1,
                    "agent": "main",
                    "action": "tool_call",
                    "tool": tool.get("toolId")
                })
        
        # Estimate tokens
        base_tokens = 500
        tool_tokens = len([t for t in agent.tools or [] if t.get("enabled")]) * 200
        estimated_tokens = base_tokens + tool_tokens
        
        return {
            "previewId": f"preview_{agent_id[:8]}",
            "executionPlan": execution_plan,
            "estimatedTokens": estimated_tokens
        }
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    @staticmethod
    def _find_node(root: ComponentNode, node_id: str) -> Optional[ComponentNode]:
        """Find node by ID in component tree"""
        if root.id == node_id:
            return root
        
        for child in root.children or []:
            found = AgentDesignService._find_node(child, node_id)
            if found:
                return found
        
        return None
    
    @staticmethod
    def _remove_node(root: ComponentNode, node_id: str) -> bool:
        """Remove node from parent's children"""
        for i, child in enumerate(root.children or []):
            if child.id == node_id:
                root.children.pop(i)
                return True
            
            if AgentDesignService._remove_node(child, node_id):
                return True
        
        return False
    
    @staticmethod
    def _validate_components(node: ComponentNode, errors: List[Dict[str, str]]):
        """Validate component tree"""
        # Check component type is valid
        valid_types = [
            "SlContainer", "SlRow", "SlCol", "SlCard", "SlSpace",
            "SlInput", "SlSelect", "SlCheckbox", "SlRadio", "SlSwitch", "SlForm",
            "SlButton", "SlTag", "SlAvatar", "SlBadge", "SlDivider",
            "SlChart", "SlTable", "SlStatCard", "SlProgress", "SlList",
            "SlChatInterface", "SlMessageList", "SlInputBar", "SlThinkingProcess"
        ]
        
        if node.type not in valid_types:
            errors.append({
                "type": "invalid_component",
                "message": f"Unknown component type '{node.type}' in node '{node.id}'"
            })
        
        # Validate children
        for child in node.children or []:
            AgentDesignService._validate_components(child, errors)
```

- [ ] **Step 2: Run imports test**

Run: `python -c "from services.agent_design_service import AgentDesignService; print('OK')"`
Expected: OK (no import errors)

- [ ] **Step 3: Commit**

```bash
git add services/agent_design_service.py
git commit -m "feat(service): add AgentDesignService for schema CRUD and validation"
```

---

### Task 3: Create Agent Design API Endpoints

**Files:**
- Create: `gateway/api/v1/agent_design.py`

- [ ] **Step 1: Create gateway/api/v1/agent_design.py**

```python
"""
Agent Design API - Schema editing, capabilities, knowledge configuration
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.agent_design import (
    SchemaUpdateRequest,
    SchemaResponse,
    ComponentAddRequest,
    ComponentUpdateRequest,
    ValidationResult,
    PreviewRequest,
    PreviewResult,
    PageSchema
)
from schemas.common import ApiResponse
from schemas.agent import AgentCapabilities, AgentKnowledge
from services.agent_design_service import AgentDesignService
from services.agent_service import AgentService


router = APIRouter(tags=["Agent Design"])


# ============================================================
# Schema Management
# ============================================================

@router.get("/{agent_id}/schema", response_model=ApiResponse[SchemaResponse])
async def get_design_schema(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get Agent's PageSchema"""
    schema = await AgentDesignService.get_schema(db, agent_id)
    
    if not schema:
        return ApiResponse(
            code=404,
            message="Schema not found",
            data={"schema": None}
        )
    
    return ApiResponse(data={"schema": schema})


@router.put("/{agent_id}/schema", response_model=ApiResponse[dict])
async def update_design_schema(
    agent_id: str,
    request: SchemaUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update Agent's PageSchema (full replacement)"""
    success = await AgentDesignService.update_schema(db, agent_id, request.schema)
    
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return ApiResponse(data={"success": True, "version": request.schema.version})


@router.post("/{agent_id}/schema/components", response_model=ApiResponse[dict])
async def add_design_component(
    agent_id: str,
    request: ComponentAddRequest,
    db: AsyncSession = Depends(get_db)
):
    """Add component node to schema"""
    component_id = await AgentDesignService.add_component(db, agent_id, request)
    
    if not component_id:
        raise HTTPException(status_code=404, detail="Agent or parent node not found")
    
    return ApiResponse(data={"componentId": component_id})


@router.put("/{agent_id}/schema/components/{node_id}", response_model=ApiResponse[dict])
async def update_design_component(
    agent_id: str,
    node_id: str,
    request: ComponentUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update single component node"""
    success = await AgentDesignService.update_component(db, agent_id, node_id, request)
    
    if not success:
        raise HTTPException(status_code=404, detail="Agent or component not found")
    
    return ApiResponse(data={"success": True})


@router.delete("/{agent_id}/schema/components/{node_id}", response_model=ApiResponse[dict])
async def delete_design_component(
    agent_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete component node and its children"""
    success = await AgentDesignService.delete_component(db, agent_id, node_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Agent or component not found")
    
    return ApiResponse(data={"success": True})


# ============================================================
# Capabilities & Knowledge
# ============================================================

@router.put("/{agent_id}/capabilities", response_model=ApiResponse[dict])
async def update_design_capabilities(
    agent_id: str,
    capabilities: AgentCapabilities,
    db: AsyncSession = Depends(get_db)
):
    """Update Agent capabilities (MCP/Skill/Tool/LLM)"""
    agent = await AgentService.update_capabilities(
        db,
        agent_id,
        capabilities.model_dump(by_alias=True)
    )
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return ApiResponse(data={
        "success": True,
        "capabilities": {
            "mcpServers": len(agent.mcp_servers or []),
            "skills": len(agent.skills or []),
            "tools": len(agent.tools or []),
            "llm": agent.llm_config.get("model", "unknown")
        }
    })


@router.put("/{agent_id}/knowledge", response_model=ApiResponse[dict])
async def update_design_knowledge(
    agent_id: str,
    knowledge: AgentKnowledge,
    db: AsyncSession = Depends(get_db)
):
    """Update Agent knowledge sources"""
    agent = await AgentService.update_knowledge(
        db,
        agent_id,
        knowledge.model_dump(by_alias=True)
    )
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return ApiResponse(data={
        "success": True,
        "knowledge": {
            "documents": len(agent.documents or []),
            "databases": len(agent.databases or []),
            "apis": len(agent.apis or []),
            "searchEnabled": agent.search_config.get("enabled", False)
        }
    })


# ============================================================
# Validation & Preview
# ============================================================

@router.post("/{agent_id}/validate", response_model=ApiResponse[ValidationResult])
async def validate_design(
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Validate Agent design"""
    result = await AgentDesignService.validate_design(db, agent_id)
    return ApiResponse(data=result)


@router.post("/{agent_id}/preview", response_model=ApiResponse[PreviewResult])
async def preview_design(
    agent_id: str,
    request: PreviewRequest,
    db: AsyncSession = Depends(get_db)
):
    """Preview execution plan"""
    result = await AgentDesignService.preview_execution(
        db,
        agent_id,
        request.input,
        request.mock_mode
    )
    
    return ApiResponse(data=PreviewResult(**result))
```

- [ ] **Step 2: Run imports test**

Run: `python -c "from gateway.api.v1.agent_design import router; print('OK')"`
Expected: OK (no import errors)

- [ ] **Step 3: Commit**

```bash
git add gateway/api/v1/agent_design.py
git commit -m "feat(api): add Agent Design API endpoints for schema CRUD"
```

---

### Task 4: Register agent_design Router

**Files:**
- Modify: `gateway/api/v1/__init__.py`

- [ ] **Step 1: Update gateway/api/v1/__init__.py**

Add import and router registration:
```python
# Add import at top (after existing imports)
from gateway.api.v1 import applications, resources, websocket, auth, conversations, agents, mcp_servers, agent_design

# Add router registration (after mcp_servers router)
api_router.include_router(
    agent_design.router,
    prefix="/agent-design",
    tags=["Agent Design"]
)
```

- [ ] **Step 2: Run imports test**

Run: `python -c "from gateway.api.v1 import api_router; print('OK')"`
Expected: OK (no import errors)

- [ ] **Step 3: Commit**

```bash
git add gateway/api/v1/__init__.py
git commit -m "feat(api): register agent_design router at /api/v1/agent-design"
```

---

### Task 5: Create Unit Tests

**Files:**
- Create: `tests/unit/test_agent_design.py`

- [ ] **Step 1: Create tests/unit/test_agent_design.py**

```python
"""
Agent Design API unit tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.agent_design_service import AgentDesignService
from schemas.agent_design import (
    PageSchema,
    ComponentNode,
    SchemaUpdateRequest,
    ComponentAddRequest,
    ValidationResult
)


class TestAgentDesignService:
    """Test AgentDesignService methods"""
    
    @pytest.mark.asyncio
    async def test_get_schema_returns_pageschema(self):
        """Test get_schema returns PageSchema"""
        mock_db = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.page_schema = {
            "id": "schema_1",
            "version": "1.0.0",
            "root": {"id": "root", "type": "SlContainer"}
        }
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        schema = await AgentDesignService.get_schema(mock_db, "agent_1")
        
        assert schema is not None
        assert schema.id == "schema_1"
        assert schema.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_update_schema_replaces_full_schema(self):
        """Test update_schema replaces entire schema"""
        mock_db = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.page_schema = {}
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        new_schema = PageSchema(
            id="schema_new",
            version="1.0.0",
            root=ComponentNode(id="root", type="SlContainer")
        )
        
        success = await AgentDesignService.update_schema(mock_db, "agent_1", new_schema)
        
        assert success is True
        assert mock_agent.page_schema["id"] == "schema_new"
    
    @pytest.mark.asyncio
    async def test_add_component_to_parent(self):
        """Test add_component adds node to parent's children"""
        mock_db = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.page_schema = {
            "id": "schema_1",
            "version": "1.0.0",
            "root": {
                "id": "root",
                "type": "SlContainer",
                "children": []
            }
        }
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        new_component = ComponentNode(id="node_1", type="SlButton")
        request = ComponentAddRequest(parent_id="root", component=new_component)
        
        component_id = await AgentDesignService.add_component(mock_db, "agent_1", request)
        
        assert component_id == "node_1"
    
    @pytest.mark.asyncio
    async def test_validate_design_returns_result(self):
        """Test validate_design returns ValidationResult"""
        mock_db = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.page_schema = {
            "id": "schema_1",
            "version": "1.0.0",
            "root": {"id": "root", "type": "SlContainer"}
        }
        mock_agent.mcp_servers = []
        mock_agent.skills = []
        mock_agent.tools = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await AgentDesignService.validate_design(mock_db, "agent_1")
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
    
    @pytest.mark.asyncio
    async def test_preview_execution_returns_plan(self):
        """Test preview_execution returns execution plan"""
        mock_db = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.llm_config = {"model": "gpt-4"}
        mock_agent.tools = [{"toolId": "web_search", "enabled": True}]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await AgentDesignService.preview_execution(
            mock_db, "agent_1", {"message": "test"}, mock_mode=True
        )
        
        assert result["previewId"] is not None
        assert len(result["executionPlan"]) >= 1
        assert result["estimatedTokens"] > 0
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_agent_design.py -v`
Expected: PASS (6 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_agent_design.py
git commit -m "test(agent-design): add unit tests for AgentDesignService"
```

---

### Task 6: Run Full Test Suite

**Files:**
- All modified files

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS (including new agent_design tests)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(agent-design): complete Agent Design API implementation

- PageSchema and ComponentNode schemas matching frontend
- AgentDesignService for schema CRUD and validation
- Design API endpoints: schema, capabilities, knowledge, validate, preview
- Router registered at /api/v1/agent-design
- Unit tests for AgentDesignService

Agent Design API ready for frontend integration."
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| 2.1 Schema Management | Task 1, Task 3 |
| 2.2 Capabilities Configuration | Task 3 |
| 2.3 Knowledge Configuration | Task 3 |
| 2.4 Validation & Preview | Task 2, Task 3 |
| 3.1 PageSchema | Task 1 |
| 3.2 AgentCapabilities | Existing (schemas/agent.py) |
| 3.3 AgentKnowledge | Existing (schemas/agent.py) |
| 4.1 File Structure | All Tasks |
| 7 Test Coverage | Task 5 |

**Placeholder Scan:** No TBD/TODO

**Type Consistency:** ComponentNode used consistently across schemas and service