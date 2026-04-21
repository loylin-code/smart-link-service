"""
Execution Management API Routes - /api/v1/executions

Endpoints for execution lifecycle management:
- Cancel execution
- Get execution status
- List execution history
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.runtime.execution import ExecutionService


router = APIRouter(prefix="/executions", tags=["Executions"])


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running execution
    
    Args:
        execution_id: Execution ID to cancel
        
    Returns:
        Cancel result with status and timestamp
        
    Raises:
        404: Execution not found
        400: Execution already completed/cancelled
    """
    service = ExecutionService(db)
    result = await service.cancel_execution(execution_id)
    
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Add execution_id to response
    result["execution_id"] = execution_id
    return result


@router.get("/{execution_id}")
async def get_execution_status(
    execution_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get execution status
    
    Args:
        execution_id: Execution ID
        
    Returns:
        Execution status dict
        
    Raises:
        404: Execution not found
    """
    service = ExecutionService(db)
    status = await service.get_execution_status(execution_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return status


@router.get("")
async def list_executions(
    agent_id: Optional[str] = Query(default=None, description="Filter by agent ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db)
):
    """
    List execution history with filters
    
    Args:
        agent_id: Filter by agent ID
        status: Filter by status value
        limit: Maximum number of results
        offset: Pagination offset
        
    Returns:
        Paginated list of executions
    """
    service = ExecutionService(db)
    items = await service.list_executions(
        agent_id=agent_id,
        status=status,
        limit=limit
    )
    
    # Return paginated structure as per API spec
    return {
        "total": len(items),
        "items": items
    }


__all__ = ["router"]