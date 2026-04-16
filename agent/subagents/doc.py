"""DocAgent - Document generation and formatting"""
from typing import Dict, Any
from datetime import datetime

from agent.subagents.base import BaseSubAgent, SubAgentCapability, SubAgentResult


class DocAgent(BaseSubAgent):
    """文档助手Agent - 文档生成、格式化"""
    
    role = "doc"
    description = "专注于文档生成、报告编写、内容格式化的Agent"
    
    capabilities = [
        SubAgentCapability(
            name="document_generation",
            description="生成文档、报告、Markdown",
            required_tools=[],  # 不需要特殊工具
            parameters_schema={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["markdown", "html", "text"]},
                    "content_type": {"type": "string"}
                },
                "required": ["content_type"]
            }
        )
    ]
    
    async def execute(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """执行文档生成任务"""
        start_time = datetime.utcnow()
        
        try:
            format_type = task.parameters.get("format", "markdown")
            content_type = task.parameters.get("content_type", "general")
            
            prompt = f"""你是一个专业的文档撰写专家。

任务: {task.description}
格式: {format_type}
内容类型: {content_type}

请生成专业文档:
1. 结构清晰
2. 内容完整
3. 格式规范（使用{format_type}格式）
"""
            
            document = await self._execute_llm(prompt)
            
            return SubAgentResult(
                success=True,
                content=document,
                metadata={"format": format_type, "content_type": content_type, "length": len(document)},
                execution_time=(datetime.utcnow() - start_time).total_seconds()
            )
            
        except Exception as e:
            return SubAgentResult(
                success=False,
                content="",
                metadata={},
                execution_time=0,
                error=str(e)
            )