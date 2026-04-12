"""Mock Agent 配置"""
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock

def get_mock_agent_config() -> Dict[str, Any]:
    """返回 Mock Agent 配置"""
    return {
        "id": "test-agent-001",
        "identity": {
            "name": "测试助手",
            "code": "test_assistant",
            "persona": "你是一个测试助手",
            "responsibilities": ["回答问题", "执行任务"]
        },
        "capabilities": {
            "skills": [{"skillId": "search", "version": "1.0.0"}],
            "mcpServers": [],
            "llm": {"provider": "openai", "model": "gpt-4", "temperature": 0.7}
        },
        "knowledge": {}
    }

def get_mock_skill():
    """返回 Mock Skill"""
    skill = MagicMock()
    skill.name = "search"
    skill.description = "搜索功能"
    skill.execute = AsyncMock(return_value={"result": "搜索结果"})
    return skill
