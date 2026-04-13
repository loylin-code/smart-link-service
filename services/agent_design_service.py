"""
Agent Design Service - Business logic for Agent page schema management
Handles schema CRUD, component operations, validation, and preview
"""
# pyright: reportGeneralTypeIssues=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportExplicitAny=false
# pyright: reportAny=false
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from services.agent_service import AgentService
from schemas.agent_design import (
    PageSchema,
    ComponentNode,
    ComponentAddRequest,
    ComponentUpdateRequest,
    ValidationResult,
)


class AgentDesignService:
    """Agent design service for schema CRUD and component operations"""
    
    # ============================================================
    # Schema CRUD Operations
    # ============================================================
    
    @staticmethod
    async def get_schema(db: AsyncSession, agent_id: str) -> PageSchema | None:
        """
        Get page schema for an agent
        
        Args:
            db: Database session
            agent_id: Agent ID
            
        Returns:
            PageSchema or None if not found
        """
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent or not agent.page_schema:
            return None
        
        # Parse page_schema dict into PageSchema object
        try:
            return PageSchema.model_validate(agent.page_schema)  # type: ignore[arg-type]
        except Exception:
            return None
    
    @staticmethod
    async def update_schema(
        db: AsyncSession,
        agent_id: str,
        schema: PageSchema
    ) -> bool:
        """
        Update agent page schema (full replacement)
        
        Args:
            db: Database session
            agent_id: Agent ID
            schema: New PageSchema to set
            
        Returns:
            True if successful, False if agent not found
        """
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            return False
        
        # Convert PageSchema to dict for storage
        agent.page_schema = schema.model_dump(by_alias=True)  # type: ignore[assignment]
        await db.flush()
        return True
    
    # ============================================================
    # Component Operations
    # ============================================================
    
    @staticmethod
    async def add_component(
        db: AsyncSession,
        agent_id: str,
        request: ComponentAddRequest
    ) -> bool:
        """
        Add a component node to the schema tree
        
        Args:
            db: Database session
            agent_id: Agent ID
            request: ComponentAddRequest with parent_id and component
            
        Returns:
            True if successful, False if agent/schema not found
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return False
        
        component = request.component
        
        # If no parent_id, add as root (replacing existing root)
        if request.parent_id is None:
            schema.root = component
        else:
            # Find parent node and add to its children
            parent = AgentDesignService._find_node(schema.root, request.parent_id)
            if not parent:
                return False
            
            if parent.children is None:
                parent.children = []
            parent.children.append(component)
        
        # Save updated schema
        return await AgentDesignService.update_schema(db, agent_id, schema)
    
    @staticmethod
    async def update_component(
        db: AsyncSession,
        agent_id: str,
        node_id: str,
        updates: ComponentUpdateRequest
    ) -> bool:
        """
        Update a component node's properties
        
        Args:
            db: Database session
            agent_id: Agent ID
            node_id: Component node ID to update
            updates: ComponentUpdateRequest with fields to update
            
        Returns:
            True if successful, False if agent/schema/node not found
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return False
        
        # Find the node to update
        node = AgentDesignService._find_node(schema.root, node_id)
        if not node:
            return False
        
        # Apply updates
        if updates.props is not None:
            if node.props is None:
                node.props = {}
            node.props.update(updates.props)
        
        if updates.style is not None:
            node.style = updates.style
        
        if updates.events is not None:
            node.events = updates.events
        
        if updates.position is not None:
            node.position = updates.position
        
        # Save updated schema
        return await AgentDesignService.update_schema(db, agent_id, schema)
    
    @staticmethod
    async def delete_component(
        db: AsyncSession,
        agent_id: str,
        node_id: str
    ) -> bool:
        """
        Delete a component node from the schema tree
        
        Args:
            db: Database session
            agent_id: Agent ID
            node_id: Component node ID to delete
            
        Returns:
            True if successful, False if agent/schema/not found or trying to delete root
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return False
        
        # Cannot delete root node
        if schema.root.id == node_id:
            return False
        
        # Remove node from parent's children
        removed = AgentDesignService._remove_node(schema.root, node_id)  # type: ignore[unused-call-result]
        if not removed:
            return False
        
        # Save updated schema
        return await AgentDesignService.update_schema(db, agent_id, schema)
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    @staticmethod
    def _find_node(root: ComponentNode, node_id: str) -> ComponentNode | None:
        """
        Find a component node in the tree by ID
        
        Args:
            root: Root node to search from
            node_id: Node ID to find
            
        Returns:
            ComponentNode or None if not found
        """
        if root.id == node_id:
            return root
        
        if root.children:
            for child in root.children:
                found = AgentDesignService._find_node(child, node_id)
                if found:
                    return found
        
        return None
    
    @staticmethod
    def _remove_node(root: ComponentNode, node_id: str) -> bool:
        """
        Remove a component node from its parent's children
        
        Args:
            root: Root node to search from
            node_id: Node ID to remove
            
        Returns:
            True if removed, False if not found
        """
        if not root.children:
            return False
        
        # Check if any direct child matches
        for i, child in enumerate(root.children):
            if child.id == node_id:
                root.children.pop(i)
                return True
        
        # Recursively search in children
        for child in root.children:
            if AgentDesignService._remove_node(child, node_id):
                return True
        
        return False
    
    @staticmethod
    def _validate_components(node: ComponentNode, errors: list[str], warnings: list[str]) -> None:
        """
        Recursively validate component nodes
        
        Args:
            node: Component node to validate
            errors: List to append error messages to
            warnings: List to append warning messages to
        """
        # Validate required fields
        if not node.id:
            errors.append(f"Component missing ID: {node.type}")
        
        if not node.type:
            errors.append(f"Component {node.id} missing type")
        
        # Validate events
        if node.events:
            for i, event in enumerate(node.events):
                if not event.event:
                    errors.append(f"Event {i} in component {node.id} missing event name")
                if event.handler:
                    if event.handler.type == 'api' and not event.handler.api:
                        errors.append(f"API event in component {node.id} missing API config")
                    if event.handler.type == 'custom' and not event.handler.code:
                        warnings.append(f"Custom event in component {node.id} has no code")
        
        # Validate children recursively
        if node.children:
            child_ids: set[str] = set()
            for child in node.children:
                # Check for duplicate IDs
                if child.id in child_ids:
                    errors.append(f"Duplicate component ID: {child.id}")
                child_ids.add(child.id)
                
                AgentDesignService._validate_components(child, errors, warnings)
    
    # ============================================================
    # Validation
    # ============================================================
    
    @staticmethod
    async def validate_design(
        db: AsyncSession,
        agent_id: str
    ) -> ValidationResult:
        """
        Validate agent design schema
        
        Args:
            db: Database session
            agent_id: Agent ID
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []
        
        # Get schema
        agent = await AgentService.get_agent_by_id(db, agent_id)
        if not agent:
            errors.append(f"Agent not found: {agent_id}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        if not agent.page_schema:  # type: ignore[arg-type]
            warnings.append("Agent has no page schema")
            return ValidationResult(valid=True, errors=errors, warnings=warnings)
        
        # Parse schema
        try:
            schema = PageSchema.model_validate(agent.page_schema)  # type: ignore[arg-type]
        except Exception as e:
            errors.append(f"Invalid schema format: {str(e)}")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Validate schema structure
        if not schema.id:
            errors.append("Schema missing ID")
        
        if not schema.version:
            warnings.append("Schema missing version")
        
        if not schema.root:
            errors.append("Schema missing root component")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Validate component tree
        AgentDesignService._validate_components(schema.root, errors, warnings)
        
        # Check for orphan components (children referencing non-existent parents)
        # This is implicitly validated by tree traversal
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    # ============================================================
    # Preview
    # ============================================================
    
    @staticmethod
    async def preview_execution(
        db: AsyncSession,
        agent_id: str,
        input_data: dict[str, Any],
        mock_mode: bool = True
    ) -> dict[str, Any]:
        """
        Generate preview execution plan for the agent design
        
        Args:
            db: Database session
            agent_id: Agent ID
            input_data: Input data for preview
            mock_mode: Use mock data instead of real execution
            
        Returns:
            Preview dict with execution plan and estimates
        """
        schema = await AgentDesignService.get_schema(db, agent_id)
        if not schema:
            return {
                "preview_id": str(uuid.uuid4()),
                "execution_plan": {
                    "status": "error",
                    "message": "No schema found"
                },
                "estimated_tokens": 0
            }
        
        # Generate execution plan from schema structure
        execution_plan = AgentDesignService._generate_execution_plan(
            schema.root,
            input_data,
            mock_mode
        )
        
        # Estimate token consumption
        estimated_tokens = AgentDesignService._estimate_tokens(schema.root)
        
        return {
            "preview_id": str(uuid.uuid4()),
            "execution_plan": execution_plan,
            "estimated_tokens": estimated_tokens
        }
    
    @staticmethod
    def _generate_execution_plan(
        root: ComponentNode,
        input_data: dict[str, Any],
        mock_mode: bool
    ) -> dict[str, Any]:
        """
        Generate execution plan from component tree
        
        Args:
            root: Root component node
            input_data: Input data for execution
            mock_mode: Use mock data
            
        Returns:
            Execution plan dict
        """
        plan: dict[str, Any] = {
            "status": "ready",
            "root": root.id,
            "components": [],
            "mock_mode": mock_mode
        }
        
        # Flatten component tree into execution order
        def collect_components(node: ComponentNode, depth: int = 0):
            component_info = {
                "id": node.id,
                "type": node.type,
                "name": node.name,
                "depth": depth,
                "has_events": bool(node.events),
                "has_children": bool(node.children),
            }
            _ = plan["components"].append(component_info)  # type: ignore[attr-defined]
            
            if node.children:
                for child in node.children:
                    collect_components(child, depth + 1)
        
        _ = collect_components(root)
        plan["total_components"] = len(plan["components"])  # type: ignore[attr-defined]
        
        # Add input data summary
        plan["input_keys"] = list(input_data.keys()) if input_data else []  # type: ignore[attr-defined]
        
        return plan
    
    @staticmethod
    def _estimate_tokens(root: ComponentNode) -> int:
        """
        Estimate token consumption for schema execution
        
        Args:
            root: Root component node
            
        Returns:
            Estimated token count
        """
        base_tokens = 100  # Base overhead
        
        def count_tokens(node: ComponentNode) -> int:
            tokens = 50  # Base per component
            
            # Add tokens for props
            if node.props:
                tokens += len(str(node.props)) // 4
            
            # Add tokens for events
            if node.events:
                for event in node.events:
                    tokens += 30  # Event handler overhead
                    if event.handler.code:
                        tokens += len(event.handler.code) // 4
            
            # Add tokens for children
            if node.children:
                for child in node.children:
                    tokens += count_tokens(child)
            
            return tokens
        
        return base_tokens + count_tokens(root)
