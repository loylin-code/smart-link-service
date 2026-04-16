"""
MessageHub - Agent communication hub with in-memory queues

Provides task dispatch, result aggregation, and agent-to-agent communication
for the SubAgent Pool execution system.

Architecture:
- MessageHub dispatches tasks to SubAgents via queues
- SubAgents receive messages, execute tasks, submit results
- MessageHub aggregates results for ExecutionPlan completion
"""
import uuid
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict
import asyncio

from pydantic import BaseModel, Field

from agent.core.plan_agent import Task, ExecutionPlan
from agent.subagents.base import SubAgentResult


class MessageType(Enum):
    """Message types for agent communication"""
    TASK_ASSIGNMENT = "task_assignment"      # Hub → SubAgent
    TASK_RESULT = "task_result"              # SubAgent → Hub
    AGENT_REQUEST = "agent_request"          # SubAgent → SubAgent
    AGENT_RESPONSE = "agent_response"        # SubAgent → SubAgent
    BROADCAST = "broadcast"                  # Hub → All Agents
    CONTROL = "control"                      # Pause, cancel, etc.


class Message(BaseModel):
    """Message for agent communication"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType
    sender: str
    recipient: Optional[str] = None  # None = broadcast
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None  # For request-response linking
    timestamp: datetime = Field(default_factory=datetime.now)
    priority: int = Field(default=0, ge=0)


class MessageHub:
    """MessageHub - Central communication hub for SubAgents
    
    Responsibilities:
    - Task dispatch to appropriate SubAgents
    - Result aggregation from SubAgent executions
    - Agent-to-agent request-response communication
    - Broadcasting messages to all agents
    
    Implementation: In-memory asyncio.Queue (single-instance deployment)
    
    Integration point: Called by AgentOrchestrator.execute_with_routing()
    """
    
    def __init__(self):
        """Initialize MessageHub with in-memory queues"""
        # Per-role message queues
        self._queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        
        # Pending results awaiting completion (correlation_id -> Future)
        self._pending_results: Dict[str, asyncio.Future] = {}
        
        # Task results storage (task_id -> SubAgentResult)
        self._task_results: Dict[str, List[SubAgentResult]] = defaultdict(list)
        
        # Active correlation IDs for tracking
        self._active_correlations: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch_task(
        self,
        task: Task,
        subagent_role: str,
        context: Dict[str, Any]
    ) -> str:
        """Dispatch a single task to a SubAgent
        
        Args:
            task: Task to dispatch
            subagent_role: Target SubAgent role
            context: Execution context
            
        Returns:
            correlation_id for tracking the task
        """
        correlation_id = str(uuid.uuid4())
        
        message = Message(
            type=MessageType.TASK_ASSIGNMENT,
            sender="hub",
            recipient=subagent_role,
            payload={
                "task": task.model_dump(),
                "context": context
            },
            correlation_id=correlation_id,
            priority=task.priority
        )
        
        # Add to role's queue
        self._queues[subagent_role].put_nowait(message)
        
        # Track correlation
        self._active_correlations[correlation_id] = {
            "task_id": task.id,
            "role": subagent_role,
            "dispatched_at": datetime.now()
        }
        
        # Create pending future for result
        self._pending_results[correlation_id] = asyncio.Future()
        
        return correlation_id
    
    async def dispatch_plan(
        self,
        plan: ExecutionPlan,
        subagent_pool: Any
    ) -> Dict[str, SubAgentResult]:
        """Dispatch and execute a complete ExecutionPlan
        
        Args:
            plan: ExecutionPlan with tasks and assignments
            subagent_pool: SubAgentPool for task execution
            
        Returns:
            Dict mapping task_id to SubAgentResult
        """
        # Order tasks by dependencies
        ordered_tasks = self._order_tasks_by_dependencies(plan.tasks)
        
        results: Dict[str, SubAgentResult] = {}
        
        # Execute tasks sequentially respecting dependencies
        for task in ordered_tasks:
            role = plan.assignments.get(task.id, "default")
            
            # Build context with previous results for dependencies
            task_context = {
                **plan.context,
                "previous_results": {
                    dep_id: results.get(dep_id)
                    for dep_id in task.dependencies
                    if dep_id in results
                }
            }
            
            # Execute task via SubAgentPool
            result = await subagent_pool.execute_task(role, task, task_context)
            results[task.id] = result
            
            # Store result
            self._task_results[task.id].append(result)
        
        return results
    
    async def collect_results(
        self,
        task_ids: List[str],
        timeout: float = 30.0
    ) -> Dict[str, SubAgentResult]:
        """Collect results for multiple tasks
        
        Args:
            task_ids: List of task IDs to collect
            timeout: Maximum wait time
            
        Returns:
            Dict mapping task_id to SubAgentResult
        """
        results = {}
        
        for task_id in task_ids:
            if task_id in self._task_results and self._task_results[task_id]:
                results[task_id] = self._task_results[task_id][-1]
        
        return results
    
    async def send_agent_request(
        self,
        sender: str,
        recipient: str,
        request: Dict[str, Any],
        timeout: float = 10.0
    ) -> str:
        """Send request from one agent to another
        
        Args:
            sender: Sender agent role
            recipient: Recipient agent role
            request: Request payload
            timeout: Maximum wait time for response
            
        Returns:
            correlation_id for tracking
        """
        correlation_id = str(uuid.uuid4())
        
        message = Message(
            type=MessageType.AGENT_REQUEST,
            sender=sender,
            recipient=recipient,
            payload=request,
            correlation_id=correlation_id
        )
        
        # Add to recipient's queue
        self._queues[recipient].put_nowait(message)
        
        # Create pending future for response
        self._pending_results[correlation_id] = asyncio.Future()
        
        return correlation_id
    
    async def broadcast(
        self,
        sender: str,
        content: Dict[str, Any]
    ) -> None:
        """Broadcast message to all agents
        
        Args:
            sender: Sender identity
            content: Broadcast content
        """
        message = Message(
            type=MessageType.BROADCAST,
            sender=sender,
            recipient=None,  # Broadcast
            payload=content
        )
        
        # Add to all known queues
        for role in self._queues.keys():
            self._queues[role].put_nowait(message)
    
    async def get_message(
        self,
        role: str,
        timeout: float = 5.0
    ) -> Optional[Message]:
        """Get next message for a role
        
        Args:
            role: SubAgent role
            timeout: Maximum wait time
            
        Returns:
            Message or None if timeout
        """
        try:
            message = await asyncio.wait_for(
                self._queues[role].get(),
                timeout=timeout
            )
            return message
        except asyncio.TimeoutError:
            return None
    
    async def submit_result(
        self,
        task_id: str,
        result: SubAgentResult,
        correlation_id: Optional[str] = None
    ) -> None:
        """Submit task result
        
        Args:
            task_id: Task ID
            result: SubAgentResult
            correlation_id: Optional correlation ID for response
        """
        # Store result
        self._task_results[task_id].append(result)
        
        # Resolve pending future if correlation_id provided
        if correlation_id and correlation_id in self._pending_results:
            future = self._pending_results[correlation_id]
            if not future.done():
                future.set_result(result)
            
            # Clean up
            del self._pending_results[correlation_id]
            if correlation_id in self._active_correlations:
                del self._active_correlations[correlation_id]
    
    def _order_tasks_by_dependencies(self, tasks: List[Task]) -> List[Task]:
        """Order tasks respecting dependencies (topological sort)
        
        Args:
            tasks: List of tasks
            
        Returns:
            Ordered list of tasks
        """
        # Build dependency graph
        task_map = {t.id: t for t in tasks}
        completed = set()
        ordered = []
        
        # Simple topological sort
        remaining = list(tasks)
        max_iterations = len(tasks) * 2  # Safety limit
        iterations = 0
        
        while remaining and iterations < max_iterations:
            iterations += 1
            
            # Find tasks with all dependencies completed
            ready = [
                t for t in remaining
                if all(dep in completed for dep in t.dependencies)
            ]
            
            if ready:
                # Sort by priority (higher first)
                ready.sort(key=lambda t: -t.priority)
                
                for task in ready:
                    ordered.append(task)
                    completed.add(task.id)
                    remaining.remove(task)
            else:
                # No ready tasks - might have circular dependency
                # Add remaining tasks anyway
                ordered.extend(remaining)
                break
        
        return ordered
    
    def get_pending_tasks(self) -> List[str]:
        """Get list of pending task IDs
        
        Returns:
            List of task IDs being processed
        """
        return list(self._active_correlations.keys())
    
    def get_queue_size(self, role: str) -> int:
        """Get queue size for a role
        
        Args:
            role: SubAgent role
            
        Returns:
            Number of messages in queue
        """
        return self._queues[role].qsize()
    
    def clear_queue(self, role: str) -> None:
        """Clear queue for a role
        
        Args:
            role: SubAgent role
        """
        while not self._queues[role].empty():
            try:
                self._queues[role].get_nowait()
            except asyncio.QueueEmpty:
                break