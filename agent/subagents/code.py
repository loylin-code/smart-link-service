"""CodeAgent - Code generation and execution"""
from typing import Dict, Any
from datetime import datetime

from agent.subagents.base import BaseSubAgent, SubAgentCapability, SubAgentResult


class CodeAgent(BaseSubAgent):
    """代码助手Agent - 代码生成、代码执行"""
    
    role = "code"
    description = "专注于代码生成、代码审查、代码执行的Agent"
    
    capabilities = [
        SubAgentCapability(
            name="code_generation",
            description="生成代码、编写函数、创建脚本",
            required_tools=["code_executor"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["python", "javascript", "typescript"]},
                    "description": {"type": "string"}
                },
                "required": ["description"]
            }
        ),
        SubAgentCapability(
            name="code_execution",
            description="执行代码、运行程序",
            required_tools=["code_executor"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string"}
                },
                "required": ["code"]
            }
        )
    ]
    
    async def execute(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """执行代码任务"""
        start_time = datetime.utcnow()
        
        try:
            intent_type = task.parameters.get("intent_type", "code_generation")
            
            if intent_type == "code_execution":
                return await self._execute_code(task, context)
            else:
                return await self._generate_code(task, context)
                
        except Exception as e:
            return SubAgentResult(
                success=False,
                content="",
                metadata={},
                execution_time=0,
                error=str(e)
            )
    
    async def _generate_code(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """生成代码"""
        language = task.parameters.get("language", "python")
        
        prompt = f"""你是一个专业的程序员。

请生成以下代码:
{task.description}

语言: {language}

要求:
1. 代码清晰、有注释
2. 包含错误处理
3. 符合最佳实践

只输出代码，不要解释。
"""
        
        code = await self._execute_llm(prompt)
        
        return SubAgentResult(
            success=True,
            content=code,
            metadata={"language": language, "type": "generated"}
        )
    
    async def _execute_code(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """执行代码"""
        code = task.parameters.get("code", "")
        language = task.parameters.get("language", "python")
        
        # 执行代码（通过toolkit）
        if self.toolkit and hasattr(self.toolkit, 'execute_tool'):
            result = await self.toolkit.execute_tool(
                "code_executor",
                {"code": code, "language": language}
            )
            return SubAgentResult(
                success=result.get("success", False),
                content=result.get("output", ""),
                metadata={"language": language, "type": "executed"},
                error=result.get("error")
            )
        
        return SubAgentResult(
            success=False,
            content="",
            metadata={},
            error="Code executor not available"
        )