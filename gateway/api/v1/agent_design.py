"""Agent Design API endpoints for schema management and agent configuration."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from schemas.agent_design import (
    SchemaUpdateRequest,
    SchemaResponse,
    ComponentAddRequest,
    ComponentUpdateRequest,
    PreviewResult,
    PreviewRequest,
)
from services.agent_design_service import AgentDesignService
from services.agent_service import AgentService


router = APIRouter(tags=["Agent Design"])


@router.get("/{agent_id}/schema")
async def get_agent_schema(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the current workflow schema for an agent."""
    schema = await AgentDesignService.get_schema(db, agent_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"data": SchemaResponse(schema=schema)}


@router.put("/{agent_id}/schema")
async def update_agent_schema(
    agent_id: str,
    request: SchemaUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fully replace the workflow schema for an agent."""
    success = await AgentDesignService.update_schema(db, agent_id, request.page_schema)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"data": {"success": True}}


@router.post("/{agent_id}/schema/components")
async def add_component(
    agent_id: str,
    request: ComponentAddRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add a new component (node/edge) to the agent schema."""
    success = await AgentDesignService.add_component(db, agent_id, request)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"data": {"success": True}}


@router.put("/{agent_id}/schema/components/{node_id}")
async def update_component(
    agent_id: str,
    node_id: str,
    request: ComponentUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update an existing component in the agent schema."""
    success = await AgentDesignService.update_component(db, agent_id, node_id, request)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} or component {node_id} not found",
        )
    return {"data": {"success": True}}


@router.delete("/{agent_id}/schema/components/{node_id}")
async def delete_component(
    agent_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a component from the agent schema."""
    success = await AgentDesignService.delete_component(db, agent_id, node_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} or component {node_id} not found",
        )
    return {"data": {"success": True}}


@router.put("/{agent_id}/capabilities")
async def update_capabilities(
    agent_id: str,
    capabilities: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update agent capabilities (MCP skills, tools, LLM config)."""
    result = await AgentService.update_capabilities(db, agent_id, capabilities)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"data": {"success": True}}


@router.put("/{agent_id}/knowledge")
async def update_knowledge(
    agent_id: str,
    knowledge: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update agent knowledge sources."""
    result = await AgentService.update_knowledge(db, agent_id, knowledge)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"data": {"success": True}}


@router.post("/{agent_id}/validate")
async def validate_schema(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Validate the agent schema for errors and inconsistencies."""
    result = await AgentDesignService.validate_design(db, agent_id)
    return {"data": result}


@router.post("/{agent_id}/preview")
async def preview_agent(
    agent_id: str,
    request: PreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate a preview of agent behavior based on current schema."""
    result = await AgentDesignService.preview_execution(
        db, agent_id, request.input, request.mock_mode
    )
    return {"data": PreviewResult(
        previewId=result["preview_id"],
        executionPlan=result["execution_plan"],
        estimatedTokens=result["estimated_tokens"],
    )}
