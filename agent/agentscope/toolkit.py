"""AgentToolkit - Skill 和 MCP 注册管理"""
from typing import Dict, Any, List
from core.exceptions import MCPError


class AgentToolkit:
    """Agent 工具包，用于注册和管理 Skill 和 MCP 工具"""

    def __init__(self):
        """初始化工具包"""
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._mcp_clients: Dict[str, Any] = {}
        self._registered_skills: Dict[str, Any] = {}
        self._registered_mcp: Dict[str, Any] = {}

    async def register_skill(self, skill: Any) -> None:
        """注册一个 Skill

        Args:
            skill: 要注册的 Skill 对象，需要有 name 属性
        """
        self._registered_skills[skill.name] = skill
        self._tools[skill.name] = {
            "type": "skill",
            "skill": skill,
            "name": skill.name,
            "description": getattr(skill, "description", ""),
            "schema": getattr(skill, "input_schema", {})
        }

    async def register_mcp_server(self, mcp_client: Any) -> None:
        """注册 MCP 客户端的工具到工具包

        Args:
            mcp_client: 已连接的 MCPClient 实例
        """
        server_name = mcp_client.config.get("name", "unknown")
        self._mcp_clients[server_name] = mcp_client

        for tool in mcp_client.tools:
            self._tools[tool.name] = {
                "type": "mcp",
                "client": mcp_client,
                "name": tool.name,
                "description": tool.description,
                "schema": tool.input_schema
            }

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 Schema（AgentScope 格式）

        Returns:
            AgentScope 格式的工具 Schema 列表：
            [
                {
                    "type": "function",
                    "function": {
                        "name": str,
                        "description": str,
                        "parameters": dict
                    }
                }
            ]
        """
        schemas = []
        for name, tool in self._tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("schema", {})
                }
            })
        return schemas

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果

        Raises:
            MCPError: 如果工具不存在或执行失败
        """
        tool = self._tools.get(name)
        if not tool:
            raise MCPError(f"Tool not found: {name}")

        tool_type = tool.get("type")

        if tool_type == "mcp":
            client = tool["client"]
            return await client.call_tool(name, arguments)

        elif tool_type == "skill":
            skill = tool.get("skill")
            if skill and hasattr(skill, "execute"):
                return await skill.execute(arguments)

        raise MCPError(f"Unknown tool type: {tool_type}")

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
