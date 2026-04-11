"""Agent Toolkit - Skill 和 MCP 注册管理"""
from typing import Dict, Any, List


class AgentToolkit:
    """Agent 工具包，用于注册和管理 Skill 和 MCP 工具"""

    def __init__(self):
        """初始化工具包"""
        self._registered_skills: Dict[str, Any] = {}
        self._registered_mcp: Dict[str, Any] = {}

    async def register_skill(self, skill: Any) -> None:
        """注册一个 Skill

        Args:
            skill: 要注册的 Skill 对象，需要有 name 属性
        """
        self._registered_skills[skill.name] = skill

    async def register_mcp(self, mcp: Any) -> None:
        """注册一个 MCP 工具

        Args:
            mcp: 要注册的 MCP 对象，需要有 name 属性
        """
        self._registered_mcp[mcp.name] = mcp

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Schema

        Returns:
            工具 Schema 列表
        """
        schemas = []
        for name, skill in self._registered_skills.items():
            schema = {
                "name": name,
                "description": getattr(skill, "description", ""),
                "type": "skill",
            }
            schemas.append(schema)
        return schemas

    def get_registered_skills(self) -> Dict[str, Any]:
        """获取所有已注册的 Skill

        Returns:
            已注册的 Skill 字典
        """
        return self._registered_skills

    def get_registered_mcp(self) -> Dict[str, Any]:
        """获取所有已注册的 MCP

        Returns:
            已注册的 MCP 字典
        """
        return self._registered_mcp
