"""Tests for BaseSubAgent abstract class"""
import pytest
from agent.subagents.base import SubAgentCapability, SubAgentResult


class TestSubAgentCapability:
    """SubAgentCapability测试"""
    
    def test_capability_creation(self):
        """测试能力创建"""
        cap = SubAgentCapability(
            name="test_cap",
            description="Test capability",
            required_tools=["tool1", "tool2"],
            parameters_schema={"type": "object", "properties": {}}
        )
        assert cap.name == "test_cap"
        assert cap.description == "Test capability"
        assert cap.required_tools == ["tool1", "tool2"]
        assert cap.parameters_schema["type"] == "object"
    
    def test_capability_defaults(self):
        """测试默认值"""
        cap = SubAgentCapability(
            name="minimal_cap",
            description="Minimal"
        )
        assert cap.required_tools == []
        assert cap.parameters_schema == {}


class TestSubAgentResult:
    """SubAgentResult测试"""
    
    def test_result_success(self):
        """测试成功结果"""
        result = SubAgentResult(
            success=True,
            content="Test output",
            metadata={"key": "value"},
            execution_time=1.5
        )
        assert result.success
        assert result.content == "Test output"
        assert result.metadata["key"] == "value"
        assert result.execution_time == 1.5
        assert result.error is None
    
    def test_result_failure(self):
        """测试失败结果"""
        result = SubAgentResult(
            success=False,
            content="",
            metadata={},
            execution_time=0,
            error="Test error"
        )
        assert not result.success
        assert result.content == ""
        assert result.error == "Test error"
    
    def test_result_defaults(self):
        """测试默认值"""
        result = SubAgentResult(success=True, content="OK")
        assert result.metadata == {}
        assert result.execution_time == 0
        assert result.error is None