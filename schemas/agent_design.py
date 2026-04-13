"""
Agent design schemas matching frontend types
Based on @smart-link/core PageSchema and ComponentNode types
"""
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# Expression & State Bindings
# ============================================================

class ExpressionBinding(BaseModel):
    """表达式绑定 - 连接状态与视图"""
    model_config = ConfigDict(populate_by_name=True)
    
    expression: str = Field(..., description="Expression value")
    type: Literal['expression', 'state', 'computed', 'method'] = Field(default='expression')


class StateBinding(BaseModel):
    """状态绑定"""
    model_config = ConfigDict(populate_by_name=True)
    
    state_key: str = Field(..., alias="stateKey", description="State path key")
    transform: Optional[Dict[str, str]] = Field(default=None, description="Get/set transform functions")


# ============================================================
# Event Handling
# ============================================================

class StateUpdateConfig(BaseModel):
    """状态更新配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    path: str
    operation: Literal['set', 'push', 'pop', 'splice', 'merge']
    value: ExpressionBinding


class ApiCallConfig(BaseModel):
    """API 调用配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    params: Optional[Dict[str, ExpressionBinding]] = None
    success: Optional['EventHandler'] = None
    error: Optional['EventHandler'] = None


class EventHandler(BaseModel):
    """事件处理器"""
    model_config = ConfigDict(populate_by_name=True)
    
    type: Literal['builtin', 'custom', 'api', 'state']
    action: Optional[Literal[
        'navigate', 'openModal', 'closeModal', 'openDrawer', 'closeDrawer',
        'submitForm', 'resetForm', 'validateForm', 'showMessage', 'hideMessage',
        'downloadFile', 'copyToClipboard', 'setVariable', 'refresh', 'back',
        'print', 'scrollTo'
    ]] = Field(default=None, description="Built-in action type")
    code: Optional[str] = Field(default=None, description="Custom code for 'custom' type")
    api: Optional[ApiCallConfig] = Field(default=None, description="API config for 'api' type")
    state_update: Optional[StateUpdateConfig] = Field(default=None, alias="stateUpdate")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Additional parameters")


class EventBinding(BaseModel):
    """事件绑定"""
    model_config = ConfigDict(populate_by_name=True)
    
    event: str
    handler: EventHandler
    modifiers: Optional[List[str]] = None


# ============================================================
# Loop & Slot Configuration
# ============================================================

class LoopConfig(BaseModel):
    """循环配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    items: str = Field(..., alias="source", description="Loop source expression")
    item_name: str = Field(..., alias="itemName", description="Current item variable name")
    index_name: Optional[str] = Field(default=None, alias="indexName", description="Index variable name")
    key: Optional[str] = Field(default=None, description="Key field for list rendering")


class SlotContent(BaseModel):
    """插槽内容"""
    model_config = ConfigDict(populate_by_name=True)
    
    type: Literal['components', 'text', 'expression']
    components: Optional[List['ComponentNode']] = None
    text: Optional[str] = None
    expression: Optional[str] = None


# ============================================================
# Style Configuration
# ============================================================

class StyleConfig(BaseModel):
    """样式配置"""
    model_config = ConfigDict(populate_by_name=True)
    
    background_color: Optional[str] = Field(default=None, alias="backgroundColor")
    border_color: Optional[str] = Field(default=None, alias="borderColor")
    border_radius: Optional[str] = Field(default=None, alias="borderRadius")
    shadow: Optional[str] = Field(default=None, description="Box shadow")
    opacity: Optional[float] = Field(default=None, ge=0, le=1)


# ============================================================
# Component Node (Recursive Model)
# ============================================================

class ComponentNode(BaseModel):
    """
    组件节点 - 树形结构
    
    Recursive model for component tree representation
    """
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    type: str
    name: Optional[str] = Field(default=None, description="Component display name")
    props: Optional[Dict[str, Any]] = Field(default=None, description="Component properties")
    style: Optional[StyleConfig] = Field(default=None, description="Component styles")
    condition: Optional[ExpressionBinding] = Field(default=None, description="Conditional rendering")
    loop: Optional[LoopConfig] = Field(default=None, description="Loop rendering config")
    events: Optional[List[EventBinding]] = Field(default=[], description="Event bindings")
    slots: Optional[Dict[str, SlotContent]] = Field(default=None, description="Slot content")
    children: Optional[List['ComponentNode']] = Field(default=[], description="Child components")
    position: Optional[Dict[str, float]] = Field(default=None, description="Position {x, y}")
    size: Optional[Dict[str, float]] = Field(default=None, description="Size {width, height}")


# Rebuild model to resolve recursive ComponentNode reference
ComponentNode.model_rebuild()


# ============================================================
# Style & Script Definitions
# ============================================================

class StyleDefinition(BaseModel):
    """样式定义"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    name: Optional[str] = Field(default=None, description="Style name")
    css: str
    scoped: Optional[bool] = Field(default=False, description="Whether style is scoped")


class ScriptDefinition(BaseModel):
    """脚本定义"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    name: Optional[str] = Field(default=None, description="Script name")
    code: str
    type: Literal['javascript', 'typescript'] = Field(default='javascript')


# ============================================================
# Page Schema
# ============================================================

class PageSchema(BaseModel):
    """
    页面 Schema - 核心渲染数据结构
    
    Main structure for agent UI design
    """
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    version: str
    root: ComponentNode
    styles: Optional[List[StyleDefinition]] = Field(default=[], description="Global styles")
    scripts: Optional[List[ScriptDefinition]] = Field(default=[], description="Custom scripts")


# ============================================================
# Request/Response Schemas
# ============================================================

class SchemaUpdateRequest(BaseModel):
    """Schema update request"""
    model_config = ConfigDict(populate_by_name=True)
    
    page_schema: PageSchema = Field(..., alias="schema", description="Page schema to update")


class SchemaResponse(BaseModel):
    """Schema response"""
    model_config = ConfigDict(populate_by_name=True)
    
    page_schema: PageSchema = Field(..., alias="schema", description="Page schema response")


class ComponentAddRequest(BaseModel):
    """Add component request"""
    model_config = ConfigDict(populate_by_name=True)
    
    parent_id: Optional[str] = Field(default=None, alias="parentId", description="Parent component ID")
    component: ComponentNode


class ComponentUpdateRequest(BaseModel):
    """Update component request"""
    model_config = ConfigDict(populate_by_name=True)
    
    props: Optional[Dict[str, Any]] = None
    style: Optional[StyleConfig] = None
    events: Optional[List[EventBinding]] = None
    position: Optional[Dict[str, float]] = None


class ValidationResult(BaseModel):
    """Validation result"""
    model_config = ConfigDict(populate_by_name=True)
    
    valid: bool
    warnings: List[str] = []
    errors: List[str] = []


class PreviewRequest(BaseModel):
    """Preview request"""
    model_config = ConfigDict(populate_by_name=True)
    
    input: Dict[str, Any] = Field(default={}, description="Preview input data")
    mock_mode: bool = Field(default=True, alias="mockMode", description="Use mock data mode")


class PreviewResult(BaseModel):
    """Preview result"""
    model_config = ConfigDict(populate_by_name=True)
    
    preview_id: str = Field(..., alias="previewId")
    execution_plan: Dict[str, Any] = Field(..., alias="executionPlan")
    estimated_tokens: int = Field(default=0, alias="estimatedTokens")
