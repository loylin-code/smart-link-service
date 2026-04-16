"""Tests for SubAgentPool and SubAgents"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.subagents.pool import SubAgentPool
from agent.subagents.research import ResearchAgent
from agent.subagents.code import CodeAgent
from agent.subagents.data import DataAgent
from agent.subagents.doc import DocAgent


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.fixture
def mock_toolkit():
    return MagicMock()


@pytest.fixture
def mock_memory():
    return AsyncMock()


@pytest.fixture
def pool(mock_llm, mock_toolkit, mock_memory):
    return SubAgentPool(mock_llm, mock_toolkit, mock_memory)


class TestSubAgentPool:
    """SubAgentPool测试"""
    
    def test_pool_initialization(self, pool):
        """测试池初始化"""
        roles = pool.get_available_roles()
        assert "research" in roles
        assert "code" in roles
        assert "data" in roles
        assert "doc" in roles
    
    def test_get_agent(self, pool):
        """测试获取Agent"""
        agent = pool.get_agent("research")
        assert agent is not None
        assert agent.role == "research"
    
    def test_get_nonexistent_agent(self, pool):
        """测试获取不存在Agent"""
        agent = pool.get_agent("nonexistent")
        assert agent is None
    
    def test_get_agent_capabilities(self, pool):
        """测试获取能力"""
        caps = pool.get_agent_capabilities("research")
        assert len(caps) > 0
        assert caps[0]["name"] in ["information_query", "knowledge_synthesis"]


class TestResearchAgent:
    """ResearchAgent测试"""
    
    def test_research_agent_role(self, mock_llm, mock_toolkit, mock_memory):
        """测试角色定义"""
        agent = ResearchAgent(mock_llm, mock_toolkit, mock_memory)
        assert agent.role == "research"
        assert len(agent.capabilities) == 2
    
    def test_research_agent_capabilities(self, mock_llm, mock_toolkit, mock_memory):
        """测试能力"""
        agent = ResearchAgent(mock_llm, mock_toolkit, mock_memory)
        cap_names = [c.name for c in agent.capabilities]
        assert "information_query" in cap_names


class TestCodeAgent:
    """CodeAgent测试"""
    
    def test_code_agent_role(self, mock_llm, mock_toolkit, mock_memory):
        """测试角色定义"""
        agent = CodeAgent(mock_llm, mock_toolkit, mock_memory)
        assert agent.role == "code"
        assert len(agent.capabilities) == 2
    
    def test_code_agent_capabilities(self, mock_llm, mock_toolkit, mock_memory):
        """测试能力"""
        agent = CodeAgent(mock_llm, mock_toolkit, mock_memory)
        cap_names = [c.name for c in agent.capabilities]
        assert "code_generation" in cap_names
        assert "code_execution" in cap_names


class TestDataAgent:
    """DataAgent测试"""
    
    def test_data_agent_role(self, mock_llm, mock_toolkit, mock_memory):
        """测试角色定义"""
        agent = DataAgent(mock_llm, mock_toolkit, mock_memory)
        assert agent.role == "data"
        assert len(agent.capabilities) == 1


class TestDocAgent:
    """DocAgent测试"""
    
    def test_doc_agent_role(self, mock_llm, mock_toolkit, mock_memory):
        """测试角色定义"""
        agent = DocAgent(mock_llm, mock_toolkit, mock_memory)
        assert agent.role == "doc"
        assert len(agent.capabilities) == 1