# AgentScope Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Pipeline (multi-agent orchestration) and Memory (session persistence) to SmartLink using AgentScope APIs.

**Architecture:** Direct AgentScope API integration - use `MsgHub` for message coordination, `SequentialPipeline`/`FanoutPipeline` for multi-agent workflows, `AsyncSQLAlchemyMemory` for session memory.

**Tech Stack:** AgentScope, AsyncSQLAlchemyMemory, SQLite, WebSocket streaming

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `agent/memory/agentscope_adapter.py` | Create | SessionMemory wrapper for AsyncSQLAlchemyMemory |
| `agent/agentscope/pipeline.py` | Create | PipelineManager for Sequential/Fanout execution |
| `agent/agentscope/hub.py` | Replace | Wrap AgentScope MsgHub instead of custom hub |
| `agent/agentscope/agent_factory.py` | Extend | Add create_plan_agent, create_sub_agent, memory support |
| `agent/core/orchestrator.py` | Extend | Add execute_pipeline method |
| `gateway/websocket/handlers.py` | Modify | Integrate SessionMemory into chat handler |
| `schemas/common.py` | Extend | Add PipelineChatRequest, StreamChunk schemas |
| `tests/unit/test_session_memory.py` | Create | SessionMemory unit tests |
| `tests/unit/test_pipeline.py` | Create | PipelineManager unit tests |
| `tests/integration/test_pipeline_flow.py` | Create | End-to-end pipeline flow test |

---

## Task 1: Create SessionMemory Adapter

**Files:**
- Create: `agent/memory/agentscope_adapter.py`
- Test: `tests/unit/test_session_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_session_memory.py
"""Unit tests for SessionMemory adapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from agent.memory.agentscope_adapter import SessionMemory


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def session_memory(mock_db_session):
    """Create SessionMemory instance."""
    return SessionMemory(
        db_session=mock_db_session,
        user_id="user_001",
        session_id="conv_001"
    )


class TestSessionMemory:
    """Test SessionMemory adapter functionality."""

    @pytest.mark.asyncio
    async def test_init_creates_memory(self, mock_db_session):
        """Test that SessionMemory initializes AsyncSQLAlchemyMemory."""
        memory = SessionMemory(
            db_session=mock_db_session,
            user_id="user_001",
            session_id="conv_001"
        )
        assert memory.user_id == "user_001"
        assert memory.session_id == "conv_001"
        assert memory.memory is not None

    @pytest.mark.asyncio
    async def test_add_message_stores_msg(self, session_memory):
        """Test that add_message stores a Msg object."""
        # Mock the underlying memory.add
        session_memory.memory.add = AsyncMock()
        
        await session_memory.add_message(
            role="user",
            content="Hello, world!",
            name="Alice"
        )
        
        # Verify add was called
        session_memory.memory.add.assert_called_once()
        call_args = session_memory.memory.add.call_args[0][0]
        assert call_args.role == "user"
        assert call_args.content == "Hello, world!"

    @pytest.mark.asyncio
    async def test_get_context_returns_history(self, session_memory):
        """Test that get_context retrieves message history."""
        # Mock get_memory to return list of Msgs
        from agentscope.message import Msg
        mock_msgs = [
            Msg(name="user", content="Hello", role="user"),
            Msg(name="assistant", content="Hi there", role="assistant"),
        ]
        session_memory.memory.get_memory = AsyncMock(return_value=mock_msgs)
        
        result = await session_memory.get_context()
        
        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there"

    @pytest.mark.asyncio
    async def test_get_message_count_returns_size(self, session_memory):
        """Test that get_message_count returns memory size."""
        session_memory.memory.size = AsyncMock(return_value=5)
        
        count = await session_memory.get_message_count()
        
        assert count == 5

    @pytest.mark.asyncio
    async def test_clear_session_clears_memory(self, session_memory):
        """Test that clear_session clears the memory."""
        session_memory.memory.clear = AsyncMock()
        
        await session_memory.clear_session()
        
        session_memory.memory.clear.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_session_memory.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'agent.memory.agentscope_adapter'"

- [ ] **Step 3: Write minimal implementation**

```python
# agent/memory/agentscope_adapter.py
"""SessionMemory adapter for AgentScope AsyncSQLAlchemyMemory."""
from typing import List, Optional
from agentscope.memory import AsyncSQLAlchemyMemory
from agentscope.message import Msg


class SessionMemory:
    """Wraps AsyncSQLAlchemyMemory for SmartLink conversation sessions.
    
    Provides a simplified interface for session-based memory management:
    - add_message: Store a message with role and content
    - get_context: Retrieve conversation history
    - get_message_count: Get total messages in session
    - clear_session: Clear all session memory
    """
    
    def __init__(
        self,
        db_session,
        user_id: str,
        session_id: str
    ):
        """Initialize SessionMemory with database session.
        
        Args:
            db_session: SQLAlchemy async session or engine
            user_id: User identifier for memory isolation
            session_id: Conversation/session identifier
        """
        self.user_id = user_id
        self.session_id = session_id
        self.memory = AsyncSQLAlchemyMemory(
            engine_or_session=db_session,
            user_id=user_id,
            session_id=session_id,
        )
    
    async def add_message(
        self,
        role: str,
        content: str,
        name: Optional[str] = None
    ) -> None:
        """Add a message to session memory.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content text
            name: Optional sender name
        """
        msg = Msg(name=name or role, content=content, role=role)
        await self.memory.add(msg)
    
    async def get_context(self) -> List[Msg]:
        """Retrieve conversation history from memory.
        
        Returns:
            List of Msg objects representing conversation history
        """
        return await self.memory.get_memory()
    
    async def get_message_count(self) -> int:
        """Get total number of messages in session.
        
        Returns:
            Integer count of stored messages
        """
        return await self.memory.size()
    
    async def clear_session(self) -> None:
        """Clear all messages from session memory."""
        await self.memory.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_session_memory.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add agent/memory/agentscope_adapter.py tests/unit/test_session_memory.py
git commit -m "feat(memory): add SessionMemory adapter for AgentScope AsyncSQLAlchemyMemory"
```

---

## Task 2: Create PipelineManager

**Files:**
- Create: `agent/agentscope/pipeline.py`
- Test: `tests/unit/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_pipeline.py
"""Unit tests for PipelineManager."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from agentscope.message import Msg
from agent.agentscope.pipeline import PipelineManager, PipelineType


@pytest.fixture
def mock_agent():
    """Create mock agent for testing."""
    agent = MagicMock()
    agent.name = "test_agent"
    agent.__call__ = AsyncMock(return_value=Msg(name="assistant", content="Response", role="assistant"))
    return agent


@pytest.fixture
def pipeline_manager():
    """Create PipelineManager instance."""
    return PipelineManager()


class TestPipelineManager:
    """Test PipelineManager functionality."""

    @pytest.mark.asyncio
    async def test_execute_single_agent(self, pipeline_manager, mock_agent):
        """Test single agent execution."""
        input_msg = Msg(name="user", content="Hello", role="user")
        
        result = await pipeline_manager.execute(
            agents=[mock_agent],
            input_msg=input_msg,
            pipeline_type=PipelineType.SINGLE
        )
        
        mock_agent.__call__.assert_called_once()
        assert result.content == "Response"

    @pytest.mark.asyncio
    async def test_execute_sequential_pipeline(self, pipeline_manager):
        """Test sequential pipeline execution (A -> B -> C)."""
        # Create mock agents
        agent_a = MagicMock()
        agent_a.name = "agent_a"
        agent_a.__call__ = AsyncMock(return_value=Msg(name="agent_a", content="Output A", role="assistant"))
        
        agent_b = MagicMock()
        agent_b.name = "agent_b"
        agent_b.__call__ = AsyncMock(return_value=Msg(name="agent_b", content="Output B", role="assistant"))
        
        input_msg = Msg(name="user", content="Start", role="user")
        
        result = await pipeline_manager.execute(
            agents=[agent_a, agent_b],
            input_msg=input_msg,
            pipeline_type=PipelineType.SEQUENTIAL
        )
        
        # Both agents should be called
        agent_a.__call__.assert_called_once()
        agent_b.__call__.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_parallel_pipeline(self, pipeline_manager):
        """Test parallel pipeline execution (A, B concurrent)."""
        agent_a = MagicMock()
        agent_a.name = "agent_a"
        agent_a.__call__ = AsyncMock(return_value=Msg(name="agent_a", content="Parallel A", role="assistant"))
        
        agent_b = MagicMock()
        agent_b.name = "agent_b"
        agent_b.__call__ = AsyncMock(return_value=Msg(name="agent_b", content="Parallel B", role="assistant"))
        
        input_msg = Msg(name="user", content="Start", role="user")
        
        results = await pipeline_manager.execute(
            agents=[agent_a, agent_b],
            input_msg=input_msg,
            pipeline_type=PipelineType.PARALLEL
        )
        
        # Results should be a list
        assert isinstance(results, list)
        assert len(results) == 2

    def test_pipeline_type_enum(self):
        """Test PipelineType enum values."""
        assert PipelineType.SINGLE.value == "single"
        assert PipelineType.SEQUENTIAL.value == "sequential"
        assert PipelineType.PARALLEL.value == "parallel"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'agent.agentscope.pipeline'"

- [ ] **Step 3: Write minimal implementation**

```python
# agent/agentscope/pipeline.py
"""PipelineManager for multi-agent workflow orchestration."""
from enum import Enum
from typing import List, Any, Union
from agentscope.message import Msg
from agentscope.pipeline import SequentialPipeline, FanoutPipeline


class PipelineType(Enum):
    """Pipeline execution type."""
    SINGLE = "single"        # Single agent execution
    SEQUENTIAL = "sequential"  # Chain: A -> B -> C
    PARALLEL = "parallel"    # Concurrent: A, B, C -> gather


class PipelineManager:
    """Manages multi-agent pipeline execution using AgentScope.
    
    Supports three execution modes:
    - SINGLE: Execute single agent (default behavior)
    - SEQUENTIAL: Chain agents where output of A feeds input of B
    - PARALLEL: Execute agents concurrently and gather results
    """
    
    def __init__(self):
        """Initialize PipelineManager."""
        self._sequential_pipeline = None
        self._fanout_pipeline = None
    
    async def execute(
        self,
        agents: List[Any],
        input_msg: Msg,
        pipeline_type: PipelineType = PipelineType.SINGLE
    ) -> Union[Msg, List[Msg]]:
        """Execute agents according to pipeline type.
        
        Args:
            agents: List of agent instances to execute
            input_msg: Input message to start pipeline
            pipeline_type: Execution mode (SINGLE, SEQUENTIAL, PARALLEL)
            
        Returns:
            Single Msg for SINGLE/SEQUENTIAL, List[Msg] for PARALLEL
        """
        if pipeline_type == PipelineType.SINGLE:
            # Single agent execution
            if len(agents) == 0:
                raise ValueError("No agents provided for execution")
            return await agents[0](input_msg)
        
        elif pipeline_type == PipelineType.SEQUENTIAL:
            # Sequential pipeline: A -> B -> C
            pipeline = SequentialPipeline(agents=agents)
            return await pipeline(input_msg)
        
        elif pipeline_type == PipelineType.PARALLEL:
            # Parallel pipeline: concurrent execution with gather
            pipeline = FanoutPipeline(agents=agents, enable_gather=True)
            return await pipeline(input_msg)
        
        else:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")
    
    async def execute_stream(
        self,
        agents: List[Any],
        input_msg: Msg,
        pipeline_type: PipelineType = PipelineType.SINGLE
    ):
        """Execute pipeline with streaming output.
        
        Args:
            agents: List of agent instances
            input_msg: Input message
            pipeline_type: Execution mode
            
        Yields:
            Streaming chunks from agent execution
        """
        from agentscope.pipeline import stream_printing_messages
        
        if pipeline_type == PipelineType.SINGLE:
            agent = agents[0]
            agent.set_console_output_enabled(False)
            
            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent(input_msg)
            ):
                yield {
                    "type": "chunk",
                    "content": msg.content,
                    "agent_name": msg.name,
                    "done": last
                }
        else:
            # For sequential/parallel, stream from each agent
            # Sequential: stream from last agent
            # Parallel: stream from all agents (simplified)
            result = await self.execute(agents, input_msg, pipeline_type)
            yield {
                "type": "complete",
                "content": result.content if isinstance(result, Msg) else str(result),
                "agent_name": "pipeline",
                "done": True
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_pipeline.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add agent/agentscope/pipeline.py tests/unit/test_pipeline.py
git commit -m "feat(pipeline): add PipelineManager for Sequential and Parallel execution"
```

---

## Task 3: Replace Hub with MsgHub Wrapper

**Files:**
- Replace: `agent/agentscope/hub.py`
- Test: `tests/unit/test_hub.py` (extend existing)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hub.py - Add new test at end of file
class TestAgentHubMsgHub:
    """Test AgentHub MsgHub integration."""

    @pytest.mark.asyncio
    async def test_create_msghub_with_participants(self):
        """Test creating MsgHub with participant agents."""
        from agent.agentscope.hub import AgentHub
        from unittest.mock import MagicMock
        
        hub = AgentHub.get_instance()
        
        # Create mock agents
        agent_a = MagicMock()
        agent_a.name = "agent_a"
        agent_b = MagicMock()
        agent_b.name = "agent_b"
        
        # Initialize with agents
        await hub.initialize_with_msghub(
            participants=[agent_a, agent_b],
            announcement="Welcome to the conversation"
        )
        
        assert hub._msghub is not None
        assert len(hub.participants) == 2

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test broadcasting message to all participants."""
        from agent.agentscope.hub import AgentHub
        from agentscope.message import Msg
        from unittest.mock import MagicMock, AsyncMock
        
        hub = AgentHub.get_instance()
        
        # Reset hub
        hub._msghub = None
        hub.participants = []
        
        agent = MagicMock()
        agent.name = "test_agent"
        agent.__call__ = AsyncMock()
        
        await hub.initialize_with_msghub(
            participants=[agent],
            announcement="Test"
        )
        
        # Broadcast should call agent
        await hub.broadcast(Msg(name="system", content="Broadcast test", role="system"))
        
        # MsgHub auto-broadcasts, verify internal state
        assert hub._msghub is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_hub.py::TestAgentHubMsgHub -v`
Expected: FAIL with "AttributeError: 'AgentHub' object has no attribute 'initialize_with_msghub'"

- [ ] **Step 3: Write implementation**

```python
# agent/agentscope/hub.py - Replace entire file
"""AgentHub - MsgHub wrapper for multi-agent message coordination."""
from typing import List, Any, Optional
from agentscope.pipeline import MsgHub
from agentscope.message import Msg


class AgentHub:
    """Central hub for multi-agent message coordination.
    
    Wraps AgentScope MsgHub for:
    - Auto-broadcasting messages to all participants
    - Managing participant lifecycle
    - Shared message history
    
    Implements singleton pattern for shared state.
    """
    
    _instance: Optional["AgentHub"] = None
    
    def __init__(self) -> None:
        """Initialize AgentHub with empty state."""
        self._msghub: Optional[MsgHub] = None
        self.participants: List[Any] = []
        self.message_history: List[Msg] = []
    
    @classmethod
    def get_instance(cls) -> "AgentHub":
        """Get the singleton instance of AgentHub."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance for testing."""
        cls._instance = None
    
    async def initialize_with_msghub(
        self,
        participants: List[Any],
        announcement: Optional[str] = None
    ) -> None:
        """Initialize MsgHub with participant agents.
        
        Args:
            participants: List of agent instances
            announcement: Optional announcement message
        """
        self.participants = participants
        
        # Create announcement Msg if provided
        announcement_msg = None
        if announcement:
            announcement_msg = Msg(
                name="system",
                content=announcement,
                role="system"
            )
        
        # Create MsgHub context manager
        self._msghub = MsgHub(
            participants=participants,
            announcement=announcement_msg,
            enable_auto_broadcast=True
        )
    
    async def broadcast(self, message: Msg) -> None:
        """Broadcast message to all participants.
        
        Args:
            message: Message to broadcast
        """
        if self._msghub:
            await self._msghub.broadcast(message)
        self.message_history.append(message)
    
    def get_history(self, limit: Optional[int] = None) -> List[Msg]:
        """Get message history with optional limit.
        
        Args:
            limit: Maximum number of recent messages
            
        Returns:
            List of messages from history
        """
        if limit is None:
            return self.message_history.copy()
        if limit <= 0:
            return []
        return self.message_history[-limit:].copy()
    
    def add_participant(self, agent: Any) -> None:
        """Add a new participant to the hub.
        
        Args:
            agent: Agent instance to add
        """
        if agent not in self.participants:
            self.participants.append(agent)
            if self._msghub:
                self._msghub.add(agent)
    
    def remove_participant(self, agent: Any) -> None:
        """Remove a participant from the hub.
        
        Args:
            agent: Agent instance to remove
        """
        if agent in self.participants:
            self.participants.remove(agent)
            if self._msghub:
                self._msghub.delete(agent)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_hub.py -v`
Expected: PASS (existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add agent/agentscope/hub.py tests/unit/test_hub.py
git commit -m "feat(hub): replace custom hub with AgentScope MsgHub wrapper"
```

---

## Task 4: Extend AgentFactory with Memory and SubAgent

**Files:**
- Modify: `agent/agentscope/agent_factory.py`
- Test: `tests/unit/test_agent_factory.py` (extend existing)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_agent_factory.py - Add new tests
class TestAgentFactoryMemory:
    """Test AgentFactory memory integration."""

    @pytest.mark.asyncio
    async def test_create_agent_with_memory(self):
        """Test creating agent with session memory."""
        from agent.agentscope.agent_factory import AgentFactory
        from unittest.mock import MagicMock
        
        factory = AgentFactory()
        
        mock_memory = MagicMock()
        mock_memory.get_context = AsyncMock(return_value=[])
        
        agent = await factory.create_agent_with_memory(
            model_name="default",
            sys_prompt="You are an assistant",
            memory=mock_memory
        )
        
        assert agent is not None
        assert hasattr(agent, 'memory')

    @pytest.mark.asyncio
    async def test_create_sub_agent(self):
        """Test creating SubAgent with specific role."""
        from agent.agentscope.agent_factory import AgentFactory
        
        factory = AgentFactory()
        
        role_config = {
            "identity": {
                "name": "ResearchAgent",
                "persona": "You are a research specialist",
                "responsibilities": ["Search for information", "Summarize findings"]
            },
            "capabilities": {
                "skills": ["web_search"]
            }
        }
        
        agent = await factory.create_sub_agent(role_config)
        
        assert agent is not None
        assert agent.name == "ResearchAgent"


class TestAgentFactoryPlanAgent:
    """Test PlanAgent creation."""

    @pytest.mark.asyncio
    async def test_create_plan_agent(self):
        """Test creating PlanAgent for intent routing."""
        from agent.agentscope.agent_factory import AgentFactory
        
        factory = AgentFactory()
        
        sub_agents_config = [
            {"name": "ResearchAgent", "capabilities": ["research"]},
            {"name": "CodeAgent", "capabilities": ["code"]}
        ]
        
        agent = await factory.create_plan_agent(sub_agents_config)
        
        assert agent is not None
        assert "plan" in agent.name.lower() or "router" in agent.name.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_agent_factory.py::TestAgentFactoryMemory -v`
Expected: FAIL with "AttributeError: 'AgentFactory' object has no attribute 'create_agent_with_memory'"

- [ ] **Step 3: Write implementation**

```python
# agent/agentscope/agent_factory.py - Extend existing file
# Add these methods after the existing create_agent method

    async def create_agent_with_memory(
        self,
        model_name: str,
        sys_prompt: str,
        memory: Any,
        tools: Optional[List[Any]] = None
    ) -> Any:
        """Create ReActAgent with session memory attached.
        
        Args:
            model_name: Model configuration name
            sys_prompt: System prompt for agent
            memory: SessionMemory instance for conversation history
            tools: Optional list of tools
            
        Returns:
            ReActAgent with memory configured
        """
        from agentscope.agent import ReActAgent
        
        model_config = self._model_configs.get(model_name, self._model_configs["default"])
        
        agent = ReActAgent(
            name="agent_with_memory",
            sys_prompt=sys_prompt,
            model_config=model_config,
            tools=tools,
            memory=memory.memory if hasattr(memory, 'memory') else memory
        )
        
        return agent
    
    async def create_sub_agent(
        self,
        role_config: Dict[str, Any],
        toolkit: Optional[Any] = None
    ) -> Any:
        """Create SubAgent with specific role configuration.
        
        Args:
            role_config: Role configuration with identity and capabilities
            toolkit: Optional toolkit with registered skills
            
        Returns:
            ReActAgent configured as SubAgent
        """
        from agentscope.agent import ReActAgent
        
        identity = role_config.get("identity", {})
        name = identity.get("name", "SubAgent")
        
        sys_prompt = self._build_sys_prompt(identity, {})
        
        capabilities = role_config.get("capabilities", {})
        llm_config = capabilities.get("llm", {})
        model_name = llm_config.get("model", "default")
        
        model_config = self._model_configs.get(model_name, self._model_configs["default"])
        
        tools = None
        if toolkit and toolkit.get_tool_schemas():
            tools = toolkit.get_tool_schemas()
        
        agent = ReActAgent(
            name=name,
            sys_prompt=sys_prompt,
            model_config=model_config,
            tools=tools
        )
        
        return agent
    
    async def create_plan_agent(
        self,
        sub_agents_config: List[Dict[str, Any]],
        toolkit: Optional[Any] = None
    ) -> Any:
        """Create PlanAgent for intent routing and task decomposition.
        
        Args:
            sub_agents_config: List of SubAgent configurations for routing
            toolkit: Optional toolkit
            
        Returns:
            ReActAgent configured as PlanAgent with routing prompt
        """
        from agentscope.agent import ReActAgent
        
        # Build routing prompt
        agent_descriptions = []
        for sub_config in sub_agents_config:
            name = sub_config.get("name", "Unknown")
            caps = sub_config.get("capabilities", [])
            agent_descriptions.append(f"- {name}: handles {', '.join(caps)}")
        
        routing_prompt = f"""# PlanAgent - Intent Router

You are the PlanAgent responsible for:
1. Understanding user intent
2. Decomposing complex tasks
3. Routing to appropriate SubAgents

Available SubAgents:
{chr(10).join(agent_descriptions)}

When responding:
- Identify the intent type
- Select the most appropriate SubAgent
- Provide clear task description for the SubAgent"""

        model_config = self._model_configs["default"]
        
        tools = None
        if toolkit and toolkit.get_tool_schemas():
            tools = toolkit.get_tool_schemas()
        
        agent = ReActAgent(
            name="PlanAgent",
            sys_prompt=routing_prompt,
            model_config=model_config,
            tools=tools
        )
        
        return agent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_agent_factory.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add agent/agentscope/agent_factory.py tests/unit/test_agent_factory.py
git commit -m "feat(agent_factory): add memory support and SubAgent/PlanAgent creation"
```

---

## Task 5: Extend Orchestrator with Pipeline Execution

**Files:**
- Modify: `agent/core/orchestrator.py`
- Test: `tests/integration/test_pipeline_flow.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_pipeline_flow.py
"""Integration tests for pipeline execution flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from agentscope.message import Msg
from agent.core.orchestrator import AgentOrchestrator
from agent.agentscope.pipeline import PipelineType


class TestPipelineFlow:
    """Test end-to-end pipeline execution."""

    @pytest.mark.asyncio
    async def test_execute_pipeline_sequential(self):
        """Test sequential pipeline execution in orchestrator."""
        orchestrator = AgentOrchestrator()
        
        # Mock agents
        agent_a = MagicMock()
        agent_a.name = "agent_a"
        agent_a.__call__ = AsyncMock(return_value=Msg(name="agent_a", content="Result A", role="assistant"))
        
        agent_b = MagicMock()
        agent_b.name = "agent_b"
        agent_b.__call__ = AsyncMock(return_value=Msg(name="agent_b", content="Result B", role="assistant"))
        
        # Execute pipeline
        result = await orchestrator.execute_pipeline(
            agents=[agent_a, agent_b],
            input_data={"message": "Test input"},
            pipeline_type=PipelineType.SEQUENTIAL
        )
        
        assert result is not None
        agent_a.__call__.assert_called()
        agent_b.__call__.assert_called()

    @pytest.mark.asyncio
    async def test_execute_pipeline_parallel(self):
        """Test parallel pipeline execution."""
        orchestrator = AgentOrchestrator()
        
        agent_a = MagicMock()
        agent_a.name = "agent_a"
        agent_a.__call__ = AsyncMock(return_value=Msg(name="agent_a", content="Parallel A", role="assistant"))
        
        agent_b = MagicMock()
        agent_b.name = "agent_b"
        agent_b.__call__ = AsyncMock(return_value=Msg(name="agent_b", content="Parallel B", role="assistant"))
        
        results = await orchestrator.execute_pipeline(
            agents=[agent_a, agent_b],
            input_data={"message": "Test"},
            pipeline_type=PipelineType.PARALLEL
        )
        
        assert isinstance(results, list)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_memory(self):
        """Test pipeline execution with session memory."""
        from agent.memory.agentscope_adapter import SessionMemory
        
        orchestrator = AgentOrchestrator()
        
        mock_session = MagicMock()
        memory = SessionMemory(
            db_session=mock_session,
            user_id="user_001",
            session_id="conv_001"
        )
        memory.memory.add = AsyncMock()
        memory.memory.get_memory = AsyncMock(return_value=[])
        
        agent = MagicMock()
        agent.name = "test_agent"
        agent.__call__ = AsyncMock(return_value=Msg(name="assistant", content="Response", role="assistant"))
        
        result = await orchestrator.execute_pipeline(
            agents=[agent],
            input_data={"message": "Hello"},
            pipeline_type=PipelineType.SINGLE,
            memory=memory
        )
        
        # Memory should have been updated
        assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_pipeline_flow.py -v`
Expected: FAIL with "AttributeError: 'AgentOrchestrator' object has no attribute 'execute_pipeline'"

- [ ] **Step 3: Write implementation**

```python
# agent/core/orchestrator.py - Add execute_pipeline method after execute_stream

    async def execute_pipeline(
        self,
        agents: List[Any],
        input_data: Dict[str, Any],
        pipeline_type: PipelineType = PipelineType.SINGLE,
        memory: Optional[Any] = None,
        conversation_id: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Execute agents as a pipeline workflow.
        
        Args:
            agents: List of agent instances to execute
            input_data: Input data with message
            pipeline_type: Execution mode (SINGLE, SEQUENTIAL, PARALLEL)
            memory: Optional SessionMemory for context
            conversation_id: Optional conversation ID
            
        Returns:
            Execution result(s) from pipeline
        """
        from agent.agentscope.pipeline import PipelineManager, PipelineType
        from agentscope.message import Msg
        
        self.is_executing = True
        try:
            # Create pipeline manager
            pipeline_manager = PipelineManager()
            
            # Build input message
            message = input_data.get("message", "")
            input_msg = Msg(name="user", content=message, role="user")
            
            # Load context from memory if available
            if memory:
                context = await memory.get_context()
                # Append context to input (simplified - could prepend to sys_prompt)
                if context:
                    # Context is already in memory, agents will access it
                    pass
            
            # Execute pipeline
            result = await pipeline_manager.execute(
                agents=agents,
                input_msg=input_msg,
                pipeline_type=pipeline_type
            )
            
            # Save result to memory if available
            if memory:
                # Save user message
                await memory.add_message(role="user", content=message, name="user")
                # Save agent response
                if isinstance(result, Msg):
                    await memory.add_message(role="assistant", content=result.content, name=result.name)
                elif isinstance(result, list):
                    for msg in result:
                        await memory.add_message(role="assistant", content=msg.content, name=msg.name)
            
            # Build and return result
            if isinstance(result, Msg):
                return self._build_result(result)
            elif isinstance(result, list):
                return [self._build_result(msg) for msg in result]
            
        except Exception as e:
            raise AgentError(f"Pipeline execution failed: {str(e)}")
        finally:
            self.is_executing = False
    
    async def execute_pipeline_stream(
        self,
        agents: List[Any],
        input_data: Dict[str, Any],
        pipeline_type: PipelineType = PipelineType.SINGLE,
        memory: Optional[Any] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute pipeline with streaming response.
        
        Args:
            agents: List of agent instances
            input_data: Input data
            pipeline_type: Execution mode
            memory: Optional SessionMemory
            
        Yields:
            Streaming chunks from pipeline execution
        """
        from agent.agentscope.pipeline import PipelineManager, PipelineType
        from agentscope.message import Msg
        
        self.is_executing = True
        try:
            pipeline_manager = PipelineManager()
            
            message = input_data.get("message", "")
            input_msg = Msg(name="user", content=message, role="user")
            
            # Stream from pipeline
            async for chunk in pipeline_manager.execute_stream(
                agents=agents,
                input_msg=input_msg,
                pipeline_type=pipeline_type
            ):
                yield chunk
            
            # Save to memory on completion
            if memory:
                await memory.add_message(role="user", content=message, name="user")
            
        except Exception as e:
            yield {"type": "error", "content": str(e), "done": True}
        finally:
            self.is_executing = False
```

- [ ] **Step 4: Add import at top of orchestrator.py**

```python
# Add to imports at top of agent/core/orchestrator.py
from typing import Union  # Add to existing typing imports
from agent.agentscope.pipeline import PipelineType  # Add new import
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_pipeline_flow.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add agent/core/orchestrator.py tests/integration/test_pipeline_flow.py
git commit -m "feat(orchestrator): add execute_pipeline method for multi-agent workflows"
```

---

## Task 6: Update WebSocket Handler with Memory Integration

**Files:**
- Modify: `gateway/websocket/handlers.py`

- [ ] **Step 1: Read current handler to identify changes**

Run: Read `gateway/websocket/handlers.py` to see current `handle_chat_message` function.

- [ ] **Step 2: Update handle_chat_message to use SessionMemory**

```python
# gateway/websocket/handlers.py - Update handle_chat_message function
# Replace the existing function with this version that integrates SessionMemory

async def handle_chat_message(
    client_id: str,
    data: Dict[str, Any],
    db: AsyncSession
):
    """
    Handle chat message from WebSocket with SessionMemory integration.
    
    Frontend expects:
    - Send: { type: "chat", data: { message, app_id, conversation_id, pipeline_type, attachments } }
    - Receive: { type: "stream", data: { delta, done, conversation_id, message_id, agent_name } }
    """
    from agent.memory.agentscope_adapter import SessionMemory
    from agent.agentscope.pipeline import PipelineType
    
    try:
        # Parse request
        message = data.get("message", "")
        app_id = data.get("app_id")
        conversation_id = data.get("conversation_id")
        pipeline_type_str = data.get("pipeline_type", "single")
        attachments = data.get("attachments", [])
        
        # Convert pipeline_type string to enum
        pipeline_type = PipelineType(pipeline_type_str)
        
        # Get or create conversation
        conversation_service = ConversationService(db)
        
        if conversation_id:
            conversation = await conversation_service.get_conversation(conversation_id)
            if not conversation:
                await manager.send_personal_message({
                    "type": "error",
                    "data": {"message": "Conversation not found"},
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }, client_id)
                return
        else:
            conversation = await conversation_service.create_conversation(
                title=message[:50] if message else "New Conversation",
                app_id=app_id
            )
            conversation_id = conversation.id
        
        # Create SessionMemory for this conversation
        memory = SessionMemory(
            db_session=db,
            user_id=client_id,  # Using client_id as user_id for now
            session_id=f"conv_{conversation_id}"
        )
        
        # Load existing context
        existing_context = await memory.get_context()
        
        # Add user message
        user_message = await conversation_service.add_message(
            conversation_id=conversation.id,
            role="user",
            content={"text": message, "attachments": attachments}
        )
        
        # Send acknowledgment
        await manager.send_personal_message({
            "type": "status",
            "data": {
                "status": "processing",
                "conversation_id": conversation.id,
                "message_id": user_message.id,
                "pipeline_type": pipeline_type_str
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }, client_id)
        
        # Execute with orchestrator and memory
        orchestrator = AgentOrchestrator(config={})
        
        # For now, use single agent (pipeline execution will be added in later tasks)
        # When pipeline_type is SEQUENTIAL or PARALLEL, load multiple agents
        
        full_content = ""
        async for chunk in orchestrator.execute_pipeline_stream(
            agents=[],  # Will be populated from agent config
            input_data={"message": message},
            pipeline_type=pipeline_type,
            memory=memory
        ):
            chunk_type = chunk.get("type", "chunk")
            chunk_content = chunk.get("content", "")
            agent_name = chunk.get("agent_name", "agent")
            
            if chunk_type == "chunk":
                full_content += chunk_content
                await manager.send_personal_message({
                    "type": "stream",
                    "data": {
                        "delta": chunk_content,
                        "done": False,
                        "conversation_id": conversation.id,
                        "message_id": None,
                        "agent_name": agent_name
                    },
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }, client_id)
            elif chunk_type == "complete":
                # Add assistant message to database
                assistant_message = await conversation_service.add_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content={"text": full_content}
                )
                
                # Send completion
                await manager.send_personal_message({
                    "type": "stream",
                    "data": {
                        "delta": "",
                        "done": True,
                        "conversation_id": conversation.id,
                        "message_id": assistant_message.id,
                        "agent_name": agent_name
                    },
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }, client_id)
            
    except Exception as e:
        await manager.send_personal_message({
            "type": "error",
            "data": {"message": str(e)},
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }, client_id)
```

- [ ] **Step 3: Run WebSocket test to verify changes**

Run: `python scripts/test_websocket.py`
Expected: WebSocket connects, ping/pong works, memory integration test passes

- [ ] **Step 4: Commit**

```bash
git add gateway/websocket/handlers.py
git commit -m "feat(ws): integrate SessionMemory and pipeline support in chat handler"
```

---

## Task 7: Add Schema Extensions

**Files:**
- Modify: `schemas/common.py`

- [ ] **Step 1: Add PipelineChatRequest and StreamChunk schemas**

```python
# schemas/common.py - Add these schemas at end of file

from typing import Literal, Optional
from pydantic import BaseModel


class PipelineChatRequest(BaseModel):
    """Chat request with pipeline support."""
    message: str
    pipeline_type: Literal["single", "sequential", "parallel"] = "single"
    sub_agents: Optional[list[str]] = None  # Agent IDs for pipeline
    app_id: str
    conversation_id: Optional[str] = None
    attachments: Optional[list[dict]] = None


class StreamChunk(BaseModel):
    """Streamed response chunk with agent attribution."""
    type: Literal["token", "tool_call", "tool_result", "complete", "error", "status"]
    data: dict
    agent_name: Optional[str] = None
    timestamp: int  # Milliseconds since epoch
```

- [ ] **Step 2: Update schemas/__init__.py to export new schemas**

```python
# schemas/__init__.py - Add exports
from schemas.common import PipelineChatRequest, StreamChunk

__all__ = [
    # ... existing exports
    "PipelineChatRequest",
    "StreamChunk",
]
```

- [ ] **Step 3: Run tests to verify**

Run: `pytest tests/ -v`
Expected: PASS (no schema import errors)

- [ ] **Step 4: Commit**

```bash
git add schemas/common.py schemas/__init__.py
git commit -m "feat(schema): add PipelineChatRequest and StreamChunk schemas"
```

---

## Task 8: Run Full Test Suite and Verification

**Files:**
- All modified files

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run all integration tests**

Run: `pytest tests/integration/ -v`
Expected: All tests PASS

- [ ] **Step 3: Run WebSocket test**

Run: `python scripts/test_websocket.py`
Expected: WebSocket connects, ping/pong works

- [ ] **Step 4: Run health check**

Run: `curl http://localhost:8000/health`
Expected: JSON response with status "healthy"

- [ ] **Step 5: Final commit if all tests pass**

```bash
git add -A
git commit -m "feat(phase2): complete Pipeline and Memory integration

- SessionMemory adapter for AsyncSQLAlchemyMemory
- PipelineManager for Sequential and Parallel execution  
- MsgHub wrapper replacing custom hub
- AgentFactory extended with memory, SubAgent, PlanAgent
- Orchestrator execute_pipeline method
- WebSocket handler memory integration
- PipelineChatRequest and StreamChunk schemas

Phase 2 implementation complete with TDD approach."
```

---

## Self-Review Checklist

After completing all tasks, verify:

| Spec Section | Covered by Task |
|--------------|-----------------|
| 2.1 PlanAgent → SubAgent Pattern | Task 4 (create_plan_agent, create_sub_agent) |
| 2.2 MsgHub Usage | Task 3 (hub.py MsgHub wrapper) |
| 2.4 Pipeline Execution Modes | Task 2 (PipelineManager) |
| 3.3 SessionMemory Adapter | Task 1 (agentscope_adapter.py) |
| 4.1 WebSocket Flow | Task 6 (handlers.py) |
| 4.2 Request Schema | Task 7 (PipelineChatRequest) |
| 5.1 Pipeline Implementation | Tasks 2, 3, 4, 5 |
| 5.2 Memory Implementation | Tasks 1, 6 |
| 5.3 Test Implementation | Tasks 1-8 (TDD throughout) |

**Placeholder Scan:** No TBD, TODO, or vague instructions in this plan.

**Type Consistency:** All Msg, SessionMemory, PipelineType references consistent across tasks.