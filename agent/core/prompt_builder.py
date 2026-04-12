"""
动态System Prompt构建器
"""
from typing import List, Dict, Any, Optional
from datetime import datetime


class SystemPromptBuilder:
    """
    动态System Prompt构建器
    
    组装顺序:
    1. 基础Prompt (Agent人格定义)
    2. 当前时间
    3. 可用工具列表
    4. 已安装Skills
    5. 记忆摘要
    6. 用户偏好
    """
    
    DEFAULT_BASE_PROMPT = """你是一个智能助手，能够理解用户需求并提供帮助。
你可以使用提供的工具来完成任务。
请用清晰、专业的方式回答用户问题。"""
    
    def __init__(self, agent_config: Dict[str, Any] = None):
        self.config = agent_config or {}
        self.base_prompt = self.config.get("base_prompt", self.DEFAULT_BASE_PROMPT)
    
    async def build(
        self,
        context: Dict[str, Any] = None,
        available_tools: List[Dict] = None,
        skills: List[Dict] = None,
        memory_summary: Optional[str] = None,
        user_preferences: Dict[str, Any] = None,
        include_time: bool = True
    ) -> str:
        """
        构建完整的System Prompt
        
        Args:
            context: 执行上下文
            available_tools: 可用工具列表
            skills: 已安装技能
            memory_summary: 记忆摘要
            user_preferences: 用户偏好
            include_time: 是否包含时间信息
            
        Returns:
            完整的System Prompt
        """
        sections = []
        
        # 1. 基础Prompt
        sections.append(self.base_prompt)
        
        # 2. 当前时间
        if include_time:
            time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sections.append(f"\n当前时间: {time_str}")
        
        # 3. 可用工具
        if available_tools:
            tool_descriptions = self._format_tools(available_tools)
            sections.append(f"\n## 可用工具\n\n{tool_descriptions}")
        
        # 4. 已安装Skills
        if skills:
            skill_descriptions = self._format_skills(skills)
            sections.append(f"\n## 已安装技能\n\n{skill_descriptions}")
        
        # 5. 记忆摘要
        if memory_summary:
            sections.append(f"\n## 相关记忆\n\n{memory_summary}")
        
        # 6. 用户偏好
        if user_preferences:
            pref_text = self._format_preferences(user_preferences)
            sections.append(f"\n## 用户偏好\n\n{pref_text}")
        
        return "\n".join(sections)
    
    def _format_tools(self, tools: List[Dict]) -> str:
        """格式化工具描述"""
        lines = []
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            lines.append(f"- **{name}**: {desc}")
            
            # 参数说明
            params = tool.get("parameters", {})
            if params:
                required = params.get("required", [])
                if required:
                    lines.append(f"  参数: {', '.join(required)}")
        
        return "\n".join(lines)
    
    def _format_skills(self, skills: List[Dict]) -> str:
        """格式化技能描述"""
        lines = []
        for skill in skills:
            name = skill.get("name", "unknown")
            desc = skill.get("description", "")
            lines.append(f"- **{name}**: {desc}")
        
        return "\n".join(lines)
    
    def _format_preferences(self, preferences: Dict) -> str:
        """格式化用户偏好"""
        lines = []
        for key, value in preferences.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def build_simple(self, context: str = None) -> str:
        """构建简单Prompt"""
        if context:
            return f"{self.base_prompt}\n\n上下文:\n{context}"
        return self.base_prompt


def create_prompt_builder(config: Dict[str, Any] = None) -> SystemPromptBuilder:
    """创建Prompt构建器"""
    return SystemPromptBuilder(config)