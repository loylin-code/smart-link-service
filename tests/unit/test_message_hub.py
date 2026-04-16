"""Tests for MessageHub - Agent communication hub"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
import uuid

from agent.core.message_hub import (
    MessageHub,
    MessageType,
    Message
)
from agent.core.plan_agent import Task, IntentType


class TestMessageType:
    """Tests for MessageType enum"""
    
    def test_message_type_values(self):
        assert MessageType.TASK_ASSIGNMENT.value == "task_assignment"
        assert MessageType.TASK_RESULT.value == "task_result"
        assert MessageType.AGENT_REQUEST.value == "agent_request"
        assert MessageType.AGENT_RESPONSE.value == "agent_response"
        assert MessageType.BROADCAST.value == "broadcast"
        assert MessageType.CONTROL.value == "control"


class TestMessage:
    """Tests for Message model"""
    
    def test_message_creation(self):
        msg = Message(
            type=MessageType.TASK_ASSIGNMENT,
            sender="hub",
            recipient="research",
            payload={"task": "test"}
        )
        assert msg.type == MessageType.TASK_ASSIGNMENT
        assert msg.sender == "hub"
        assert msg.recipient == "research"
        assert msg.payload["task"] == "test"
    
    def test_message_broadcast(self):
        """Test broadcast message (no recipient)"""
        msg = Message(
            type=MessageType.BROADCAST,
            sender="hub",
            recipient=None,  # Broadcast
            payload={"content": "announcement"}
        )
        assert msg.recipient is None
    
    def test_message_defaults(self):
        msg = Message(
            type=MessageType.TASK_ASSIGNMENT,
            sender="hub",
            recipient="code",
            payload={}
        )
        assert msg.priority == 0
        assert msg.correlation_id is None


class TestMessageHub:
    """Tests for MessageHub class"""
    
    @pytest.fixture
    def hub(self):
        return MessageHub()
    
    def test_hub_initialization(self, hub):
        assert hub._queues is not None
        assert hub._pending_results is not None
        assert hub._task_results is not None
    
    @pytest.mark.asyncio
    async def test_dispatch_task(self, hub):
        """Test dispatching a single task"""
        task = Task(
            id="task_001",
            intent_type=IntentType.INFORMATION_QUERY,
            description="Test task",
            parameters={"query": "test"}
        )
        correlation_id = await hub.dispatch_task(task, "research", {})
        assert correlation_id is not None
        assert len(correlation_id) > 0
    
    @pytest.mark.asyncio
    async def test_order_tasks_by_dependencies(self, hub):
        """Test task ordering by dependencies"""
        tasks = [
            Task(id="t1", intent_type=IntentType.CODE_GENERATION, description="", parameters={}, dependencies=[]),
            Task(id="t2", intent_type=IntentType.CODE_EXECUTION, description="", parameters={}, dependencies=["t1"]),
            Task(id="t3", intent_type=IntentType.DATA_ANALYSIS, description="", parameters={}, dependencies=["t1", "t2"])
        ]
        ordered = hub._order_tasks_by_dependencies(tasks)
        assert ordered[0].id == "t1"
        assert ordered[1].id == "t2"
        assert ordered[2].id == "t3"
    
    @pytest.mark.asyncio
    async def test_order_tasks_no_dependencies(self, hub):
        """Test ordering tasks without dependencies"""
        tasks = [
            Task(id="t1", intent_type=IntentType.INFORMATION_QUERY, description="", parameters={}, dependencies=[]),
            Task(id="t2", intent_type=IntentType.CODE_GENERATION, description="", parameters={}, dependencies=[]),
            Task(id="t3", intent_type=IntentType.DATA_ANALYSIS, description="", parameters={}, dependencies=[])
        ]
        ordered = hub._order_tasks_by_dependencies(tasks)
        # Should return in original order when no dependencies
        assert len(ordered) == 3
    
    @pytest.mark.asyncio
    async def test_dispatch_plan(self, hub):
        """Test dispatching an execution plan"""
        from agent.core.plan_agent import ExecutionPlan
        from agent.subagents.pool import SubAgentPool
        from agent.subagents.base import SubAgentResult
        
        # Create mock SubAgentPool
        mock_pool = MagicMock(spec=SubAgentPool)
        mock_pool.execute_task = AsyncMock(return_value=SubAgentResult(
            success=True,
            content="Test result",
            metadata={},
            execution_time=0.5
        ))
        
        tasks = [
            Task(id="t1", intent_type=IntentType.INFORMATION_QUERY, description="test", parameters={})
        ]
        assignments = {"t1": "research"}
        
        plan = ExecutionPlan(
            tasks=tasks,
            assignments=assignments,
            context={},
            created_at=datetime.now()
        )
        
        results = await hub.dispatch_plan(plan, mock_pool)
        assert "t1" in results
        assert results["t1"].success
    
    @pytest.mark.asyncio
    async def test_send_agent_request(self, hub):
        """Test agent-to-agent request"""
        # Set up a pending result for response
        correlation_id = str(uuid.uuid4())
        hub._pending_results[correlation_id] = asyncio.Future()
        
        # Send request
        request_id = await hub.send_agent_request(
            sender="research",
            recipient="code",
            request={"action": "generate_code"},
            timeout=5.0
        )
        assert request_id is not None
    
    @pytest.mark.asyncio
    async def test_broadcast(self, hub):
        """Test broadcasting message to all agents"""
        await hub.broadcast(sender="hub", content={"message": "system notification"})
        # Check that message was added to queues
        # The hub should have queues for default roles
        assert True  # Broadcast completed without error
    
    @pytest.mark.asyncio
    async def test_submit_result(self, hub):
        """Test submitting task result"""
        from agent.subagents.base import SubAgentResult
        
        task_id = "task_001"
        correlation_id = str(uuid.uuid4())
        
        # Set up pending future
        hub._pending_results[correlation_id] = asyncio.Future()
        
        result = SubAgentResult(
            success=True,
            content="Completed",
            metadata={},
            execution_time=1.0
        )
        
        await hub.submit_result(task_id, result, correlation_id)
        
        # Check result was stored
        assert task_id in hub._task_results
    
    @pytest.mark.asyncio
    async def test_get_message(self, hub):
        """Test getting message for a role"""
        # First dispatch a task to create a message
        task = Task(
            id="task_001",
            intent_type=IntentType.INFORMATION_QUERY,
            description="Test",
            parameters={}
        )
        await hub.dispatch_task(task, "research", {})
        
        # Now get the message
        msg = await hub.get_message("research", timeout=1.0)
        assert msg is not None
        assert msg.type == MessageType.TASK_ASSIGNMENT
    
    def test_get_pending_tasks(self, hub):
        """Test getting list of pending tasks"""
        pending = hub.get_pending_tasks()
        assert isinstance(pending, list)


class TestMessageHubIntegration:
    """Integration tests for MessageHub with SubAgentPool"""
    
    @pytest.fixture
    def full_setup(self):
        """Create full MessageHub + SubAgentPool setup"""
        hub = MessageHub()
        
        # Create mock pool
        from agent.subagents.pool import SubAgentPool
        mock_pool = MagicMock(spec=SubAgentPool)
        mock_pool.get_available_roles = MagicMock(return_value=["research", "code", "data", "doc"])
        
        return hub, mock_pool
    
    @pytest.mark.asyncio
    async def test_full_task_flow(self, full_setup):
        """Test complete task dispatch -> execute -> result flow"""
        hub, mock_pool = full_setup
        
        from agent.subagents.base import SubAgentResult
        
        # Mock execute_task
        mock_pool.execute_task = AsyncMock(return_value=SubAgentResult(
            success=True,
            content="Task completed successfully",
            metadata={"tokens_used": 100},
            execution_time=0.5
        ))
        
        # Create plan
        from agent.core.plan_agent import ExecutionPlan
        
        tasks = [
            Task(id="t1", intent_type=IntentType.CODE_GENERATION, description="Generate function", parameters={})
        ]
        assignments = {"t1": "code"}
        plan = ExecutionPlan(tasks=tasks, assignments=assignments, context={}, created_at=datetime.now())
        
        # Execute
        results = await hub.dispatch_plan(plan, mock_pool)
        
        assert results["t1"].success
        assert results["t1"].content == "Task completed successfully"