"""Tests for PlanAgent - Intent recognition and routing"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from agent.core.plan_agent import (
    PlanAgent,
    IntentType,
    Intent,
    Task,
    ExecutionPlan
)


class TestIntentType:
    """Tests for IntentType enum"""
    
    def test_intent_type_values(self):
        assert IntentType.INFORMATION_QUERY.value == "information_query"
        assert IntentType.CODE_GENERATION.value == "code_generation"
        assert IntentType.CODE_EXECUTION.value == "code_execution"
        assert IntentType.DATA_ANALYSIS.value == "data_analysis"
        assert IntentType.DOCUMENT_GENERATION.value == "document_generation"
        assert IntentType.CONVERSATION.value == "conversation"
        assert IntentType.MULTI_STEP.value == "multi_step"


class TestIntent:
    """Tests for Intent model"""
    
    def test_intent_creation(self):
        intent = Intent(
            type=IntentType.INFORMATION_QUERY,
            confidence=0.85,
            entities={"query": "Python教程"},
            parameters={"query": "Python教程"},
            raw_input="帮我查询Python教程"
        )
        assert intent.type == IntentType.INFORMATION_QUERY
        assert intent.confidence == 0.85
        assert intent.entities["query"] == "Python教程"
    
    def test_intent_default_values(self):
        intent = Intent(
            type=IntentType.CONVERSATION,
            confidence=0.5,
            entities={},
            parameters={},
            raw_input="你好"
        )
        assert intent.entities == {}
        assert intent.parameters == {}


class TestTask:
    """Tests for Task model"""
    
    def test_task_creation(self):
        task = Task(
            id="task_001",
            intent_type=IntentType.CODE_GENERATION,
            description="Generate a Python function",
            parameters={"function_name": "calculate_sum"}
        )
        assert task.id == "task_001"
        assert task.intent_type == IntentType.CODE_GENERATION
        assert task.dependencies == []
        assert task.priority == 0
    
    def test_task_with_dependencies(self):
        task = Task(
            id="task_002",
            intent_type=IntentType.CODE_EXECUTION,
            description="Execute the generated code",
            parameters={},
            dependencies=["task_001"]
        )
        assert task.dependencies == ["task_001"]


class TestExecutionPlan:
    """Tests for ExecutionPlan model"""
    
    def test_execution_plan_creation(self):
        tasks = [
            Task(id="t1", intent_type=IntentType.INFORMATION_QUERY, description="test", parameters={}),
            Task(id="t2", intent_type=IntentType.CODE_GENERATION, description="test", parameters={})
        ]
        assignments = {"t1": "research", "t2": "code"}
        
        plan = ExecutionPlan(
            tasks=tasks,
            assignments=assignments,
            context={"conversation_id": "conv_001"},
            created_at=datetime.now()
        )
        assert len(plan.tasks) == 2
        assert plan.assignments["t1"] == "research"
        assert plan.assignments["t2"] == "code"


class TestPlanAgent:
    """Tests for PlanAgent class"""
    
    @pytest.fixture
    def plan_agent(self):
        llm = AsyncMock()
        memory = AsyncMock()
        return PlanAgent(llm, memory)
    
    def test_plan_agent_initialization(self, plan_agent):
        assert plan_agent.llm is not None
        assert plan_agent.memory is not None
    
    def test_routing_map(self, plan_agent):
        """Test routing map is correctly initialized"""
        assert plan_agent.routing_map[IntentType.INFORMATION_QUERY] == "research"
        assert plan_agent.routing_map[IntentType.CODE_GENERATION] == "code"
        assert plan_agent.routing_map[IntentType.CODE_EXECUTION] == "code"
        assert plan_agent.routing_map[IntentType.DATA_ANALYSIS] == "data"
        assert plan_agent.routing_map[IntentType.DOCUMENT_GENERATION] == "doc"
        assert plan_agent.routing_map[IntentType.CONVERSATION] == "default"
    
    def test_route_tasks(self, plan_agent):
        """Test task routing logic"""
        tasks = [
            Task(id="t1", intent_type=IntentType.INFORMATION_QUERY, description="test", parameters={}),
            Task(id="t2", intent_type=IntentType.CODE_GENERATION, description="test", parameters={}),
            Task(id="t3", intent_type=IntentType.DATA_ANALYSIS, description="test", parameters={})
        ]
        assignments = plan_agent.route_tasks(tasks)
        assert assignments["t1"] == "research"
        assert assignments["t2"] == "code"
        assert assignments["t3"] == "data"
    
    @pytest.mark.asyncio
    async def test_process_simple_intent(self, plan_agent):
        """Test processing a simple intent"""
        # Mock LLM response for intent recognition
        plan_agent.llm.chat = AsyncMock(return_value='{"intent_type": "information_query", "confidence": 0.9, "entities": {"query": "test"}, "parameters": {"query": "test"}}')
        
        # Mock memory to return empty history
        plan_agent.memory.get_context_for_plan_agent = AsyncMock(return_value=MagicMock(
            messages=[],
            summary=None,
            key_entities={},
            token_count=0
        ))
        
        plan = await plan_agent.process(
            user_input="查询Python教程",
            conversation_id="conv_001",
            context={}
        )
        
        assert plan is not None
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.tasks) >= 1
    
    @pytest.mark.asyncio
    async def test_decompose_single_intent(self, plan_agent):
        """Test decomposition of single intent"""
        intent = Intent(
            type=IntentType.INFORMATION_QUERY,
            confidence=0.9,
            entities={"query": "test"},
            parameters={"query": "test"},
            raw_input="查询测试"
        )
        tasks = await plan_agent.decompose_task(intent, {})
        assert len(tasks) == 1
        assert tasks[0].intent_type == IntentType.INFORMATION_QUERY
    
    @pytest.mark.asyncio
    async def test_decompose_multi_step_intent(self, plan_agent):
        """Test decomposition of multi-step intent"""
        # Mock LLM for task decomposition
        plan_agent.llm.chat = AsyncMock(return_value='[{"id": "t1", "intent_type": "code_generation", "description": "Step 1", "parameters": {}}, {"id": "t2", "intent_type": "code_execution", "description": "Step 2", "parameters": {}, "dependencies": ["t1"]}]')
        
        intent = Intent(
            type=IntentType.MULTI_STEP,
            confidence=0.8,
            entities={"steps": 2},
            parameters={"steps": 2},
            raw_input="生成并执行代码"
        )
        
        tasks = await plan_agent.decompose_task(intent, {})
        assert len(tasks) >= 1
    
    def test_build_intent_prompt(self, plan_agent):
        """Test intent prompt building"""
        prompt = plan_agent._build_intent_prompt(
            user_input="查询Python教程",
            history=[{"role": "user", "content": "你好"}]
        )
        assert "查询Python教程" in prompt
        assert "intent_type" in prompt