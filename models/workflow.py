"""
Workflow models for SmartLink
Includes Workflow, WorkflowNode, WorkflowEdge models
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, JSON, DateTime, Integer, 
    Boolean, Enum as SQLEnum, ForeignKey, Index
)
from sqlalchemy.orm import relationship
import enum
import uuid

from db.session import Base
from core.time_utils import now_utc8


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class WorkflowStatus(str, enum.Enum):
    """Workflow status enum"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class NodeType(str, enum.Enum):
    """Workflow node types"""
    START = "start"           # Entry point
    END = "end"               # Exit point
    LLM = "llm"               # LLM call
    SKILL = "skill"           # Skill execution
    TOOL = "tool"             # Tool/MCP execution
    CONDITION = "condition"   # Conditional branch
    PARALLEL = "parallel"     # Parallel execution
    LOOP = "loop"             # Loop/iteration
    CODE = "code"             # Custom code execution
    HTTP = "http"             # HTTP request
    TRANSFORM = "transform"   # Data transformation
    HUMAN = "human"           # Human in the loop
    VARIABLE = "variable"     # Variable assignment


class Workflow(Base):
    """
    Workflow model
    Defines a structured agent workflow with nodes and edges
    """
    __tablename__ = "workflows"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(String, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Workflow info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(20), default="1.0.0", nullable=False)
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.DRAFT, nullable=False)
    
    # Trigger configuration
    trigger_type = Column(String(50), default="manual", nullable=False)  # manual, webhook, schedule, event
    trigger_config = Column(JSON, default=dict, nullable=False)
    
    # Input/Output schema
    input_schema = Column(JSON, default=dict, nullable=False)
    output_schema = Column(JSON, default=dict, nullable=False)
    
    # Execution settings
    timeout_seconds = Column(Integer, default=300, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    retry_delay_seconds = Column(Integer, default=5, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=now_utc8, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    nodes = relationship("WorkflowNode", back_populates="workflow", cascade="all, delete-orphan")
    edges = relationship("WorkflowEdge", back_populates="workflow", cascade="all, delete-orphan")
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_workflows_tenant_status', 'tenant_id', 'status'),
    )
    
    def __repr__(self):
        return f"<Workflow(id={self.id}, name={self.name}, status={self.status})>"


class WorkflowNode(Base):
    """
    Workflow node model
    Represents a single step in the workflow
    """
    __tablename__ = "workflow_nodes"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Node identification
    node_id = Column(String(100), nullable=False)  # User-defined node ID (e.g., "llm_1", "skill_search")
    node_type = Column(SQLEnum(NodeType), nullable=False)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # Node configuration
    config = Column(JSON, default=dict, nullable=False)  # Node-specific configuration
    
    # Position for visual editor
    position_x = Column(Integer, default=0, nullable=False)
    position_y = Column(Integer, default=0, nullable=False)
    
    # Execution settings
    timeout_seconds = Column(Integer, nullable=True)  # Override workflow timeout
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=now_utc8, nullable=True)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="nodes")
    
    # Indexes
    __table_args__ = (
        Index('ix_workflow_nodes_workflow_node_id', 'workflow_id', 'node_id', unique=True),
    )
    
    def __repr__(self):
        return f"<WorkflowNode(id={self.id}, node_id={self.node_id}, type={self.node_type})>"
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)


class WorkflowEdge(Base):
    """
    Workflow edge model
    Defines connections between nodes
    """
    __tablename__ = "workflow_edges"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Edge identification
    edge_id = Column(String(100), nullable=False)  # User-defined edge ID
    
    # Source and target
    source_node_id = Column(String(100), nullable=False)  # References workflow_nodes.node_id
    target_node_id = Column(String(100), nullable=False)
    
    # Condition for conditional edges
    condition_type = Column(String(50), nullable=True)  # always, expression, output_match
    condition_expression = Column(Text, nullable=True)  # Expression for condition
    condition_label = Column(String(100), nullable=True)  # Label for visual editor (e.g., "Yes", "No")
    
    # Edge metadata
    order = Column(Integer, default=0, nullable=False)  # Order for multiple edges from same node
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="edges")
    
    # Indexes
    __table_args__ = (
        Index('ix_workflow_edges_workflow_edge_id', 'workflow_id', 'edge_id', unique=True),
        Index('ix_workflow_edges_source', 'workflow_id', 'source_node_id'),
        Index('ix_workflow_edges_target', 'workflow_id', 'target_node_id'),
    )
    
    def __repr__(self):
        return f"<WorkflowEdge(id={self.id}, {self.source_node_id} -> {self.target_node_id})>"


class ExecutionStatus(str, enum.Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class WorkflowExecution(Base):
    """
    Workflow execution model
    Tracks execution history and state
    """
    __tablename__ = "workflow_executions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Execution info
    status = Column(SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False)
    triggered_by = Column(String, nullable=True)  # user_id, webhook_id, schedule_id
    trigger_type = Column(String(50), nullable=True)
    
    # Input/Output
    input_data = Column(JSON, default=dict, nullable=False)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    error_node_id = Column(String(100), nullable=True)  # Node where error occurred
    
    # Execution state
    current_node_id = Column(String(100), nullable=True)
    node_states = Column(JSON, default=dict, nullable=False)  # State of each node
    variables = Column(JSON, default=dict, nullable=False)  # Workflow variables
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Token usage
    total_prompt_tokens = Column(Integer, default=0, nullable=False)
    total_completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=now_utc8, nullable=True)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    node_executions = relationship("NodeExecution", back_populates="workflow_execution", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_workflow_executions_tenant_status', 'tenant_id', 'status'),
        Index('ix_workflow_executions_workflow_status', 'workflow_id', 'status'),
    )
    
    def __repr__(self):
        return f"<WorkflowExecution(id={self.id}, status={self.status})>"


class NodeExecution(Base):
    """
    Node execution model
    Tracks individual node execution within a workflow
    """
    __tablename__ = "node_executions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_execution_id = Column(String, ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Node info
    node_id = Column(String(100), nullable=False)
    node_type = Column(String(50), nullable=False)
    
    # Execution info
    status = Column(SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Token usage (for LLM nodes)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_utc8, nullable=False)
    
    # Relationships
    workflow_execution = relationship("WorkflowExecution", back_populates="node_executions")
    
    # Indexes
    __table_args__ = (
        Index('ix_node_executions_workflow_node', 'workflow_execution_id', 'node_id'),
    )
    
    def __repr__(self):
        return f"<NodeExecution(id={self.id}, node_id={self.node_id}, status={self.status})>"