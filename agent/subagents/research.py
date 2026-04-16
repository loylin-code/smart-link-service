"""ResearchAgent - Information retrieval and knowledge synthesis"""
from typing import Dict, Any
from datetime import datetime

from agent.subagents.base import BaseSubAgent, SubAgentCapability, SubAgentResult


class ResearchAgent(BaseSubAgent):
    """研究分析Agent - 信息检索、知识整合"""
    
    role = "research"
    description = "专注于信息检索、知识整合、数据分析的研究Agent"
    
    capabilities = [
        SubAgentCapability(
            name="information_query",
            description="查询信息、检索知识",
            required_tools=["web_search"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        ),
        SubAgentCapability(
            name="knowledge_synthesis",
            description="整合多方信息、生成综合报告",
            required_tools=["web_search"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "topics": {"type": "array"}
                }
            }
        )
    ]
    
    async def execute(
        self,
        task: 'Task',
        context: Dict[str, Any]
    ) -> SubAgentResult:
        """执行研究任务"""
        start_time = datetime.utcnow()
        
        try:
            # 1. 准备上下文
            conversation_id = context.get("conversation_id")
            history = await self._prepare_context(conversation_id) if conversation_id else []
            
            # 2. 构建研究prompt
            prompt = self._build_research_prompt(task, history)
            
            # 3. 获取研究工具
            tools = self.toolkit.get_tool_schemas(["web_search"]) if self.toolkit else None
            
            # 4. 执行LLM
            response = await self._execute_llm(prompt, tools)
            
            # 5. 返回结果
            return SubAgentResult(
                success=True,
                content=response,
                metadata={"sources": [], "query": task.parameters.get("query")},
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
    
    def _build_research_prompt(
        self,
        task: 'Task',
        history: list
    ) -> str:
        """构建研究prompt"""
        history_text = "\n".join([
            f"{h.get('role', 'user')}: {h.get('content', '')}"
            for h in history[-5:]  # 最近5条
        ]) if history else "无历史对话"
        
        return f"""你是一个专业的研究分析师。

任务: {task.description}
查询: {task.parameters.get('query', '未指定')}

历史对话:
{history_text}

请检索相关信息并整合生成分析报告。使用web_search工具查询必要信息。
"""