"""DataAgent - Data analysis and visualization"""
from typing import Dict, Any
from datetime import datetime

from agent.subagents.base import BaseSubAgent, SubAgentCapability, SubAgentResult


class DataAgent(BaseSubAgent):
    """数据分析Agent - 数据处理、可视化"""
    
    role = "data"
    description = "专注于数据分析、统计计算、可视化生成的Agent"
    
    capabilities = [
        SubAgentCapability(
            name="data_analysis",
            description="数据分析、统计分析",
            required_tools=["code_executor"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "data_source": {"type": "string"},
                    "analysis_type": {"type": "string"}
                },
                "required": ["analysis_type"]
            }
        )
    ]
    
    async def execute(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """执行数据分析任务"""
        start_time = datetime.utcnow()
        
        try:
            analysis_type = task.parameters.get("analysis_type", "general")
            data_source = task.parameters.get("data_source", "用户提供")
            
            # 生成Python分析代码
            prompt = f"""你是一个数据分析师。

分析任务: {task.description}
分析类型: {analysis_type}
数据源: {data_source}

请生成Python pandas分析代码:
1. 数据加载
2. 数据处理
3. 统计分析
4. 结果输出

输出可执行的Python代码。
"""
            
            analysis_code = await self._execute_llm(prompt)
            
            # 执行代码
            if self.toolkit and hasattr(self.toolkit, 'execute_tool'):
                execution_result = await self.toolkit.execute_tool(
                    "code_executor",
                    {"code": analysis_code, "language": "python"}
                )
                
                return SubAgentResult(
                    success=execution_result.get("success", False),
                    content=execution_result.get("output", ""),
                    metadata={"analysis_type": analysis_type, "data_source": data_source},
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                    error=execution_result.get("error")
                )
            
            return SubAgentResult(
                success=True,
                content=analysis_code,
                metadata={"analysis_type": analysis_type, "type": "code_only"},
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