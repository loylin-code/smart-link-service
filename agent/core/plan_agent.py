"""
PlanAgent - Intent recognition and routing layer

Acts as a pre-routing layer before AgentOrchestrator:
- Recognizes user intent using LLM
- Decomposes complex tasks into atomic tasks
- Routes tasks to appropriate SubAgents
"""
import json
import uuid
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class IntentType(Enum):
    """Intent classification types"""
    INFORMATION_QUERY = "information_query"
    CODE_GENERATION = "code_generation"
    CODE_EXECUTION = "code_execution"
    DATA_ANALYSIS = "data_analysis"
    DOCUMENT_GENERATION = "document_generation"
    CONVERSATION = "conversation"
    MULTI_STEP = "multi_step"


class Intent(BaseModel):
    """Recognized intent from user input"""
    type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    raw_input: str


class Task(BaseModel):
    """Atomic task for SubAgent execution"""
    id: str
    intent_type: IntentType
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0)


class ExecutionPlan(BaseModel):
    """Complete execution plan with tasks and routing"""
    tasks: List[Task]
    assignments: Dict[str, str]  # task_id -> subagent_role
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


INTENT_PROMPT_TEMPLATE = """你是一个意图识别系统。

可用意图类型:
- information_query: 信息查询、知识检索、搜索
- code_generation: 生成代码、编写函数、创建脚本
- code_execution: 执行代码、运行程序、测试代码
- data_analysis: 数据分析、统计分析、生成图表
- document_generation: 生成文档、写报告、格式化文本
- conversation: 闲聊、问候、简单对话
- multi_step: 多步骤任务、复合任务

历史对话:
{history}

用户输入: {user_input}

请以JSON格式返回:
{{
    "intent_type": "<意图类型>",
    "confidence": <0.0-1.0>,
    "entities": {{<key>: <value>}},
    "parameters": {{<key>: <value>}}
}}

只返回JSON。"""

DECOMPOSE_PROMPT_TEMPLATE = """你是一个任务分解系统。

用户请求是一个多步骤任务，请将其分解为原子任务。

原始输入: {raw_input}
识别的意图: {intent_type}
已提取参数: {parameters}

请将任务分解为独立的原子步骤，以JSON数组格式返回:
[
    {{
        "id": "task_<n>",
        "intent_type": "<意图类型>",
        "description": "<任务描述>",
        "parameters": {{<key>: <value>}},
        "dependencies": ["task_<m>"],  // 如果依赖其他任务
        "priority": 0
    }}
]

只返回JSON数组。"""


class PlanAgent:
    """PlanAgent - Pre-routing layer for intelligent task processing
    
    Responsibilities:
    - Intent recognition using LLM
    - Task decomposition for complex requests
    - Routing decisions to appropriate SubAgents
    
    Integration point: Called by AgentOrchestrator.execute_with_routing()
    """
    
    def __init__(self, llm_client: Any, memory_manager: Any):
        """Initialize PlanAgent
        
        Args:
            llm_client: LLM client for intent recognition
            memory_manager: Memory manager for context retrieval
        """
        self.llm = llm_client
        self.memory = memory_manager
        
        # Routing map: IntentType -> SubAgent role
        self.routing_map: Dict[IntentType, str] = {
            IntentType.INFORMATION_QUERY: "research",
            IntentType.CODE_GENERATION: "code",
            IntentType.CODE_EXECUTION: "code",
            IntentType.DATA_ANALYSIS: "data",
            IntentType.DOCUMENT_GENERATION: "doc",
            IntentType.CONVERSATION: "default",
            IntentType.MULTI_STEP: "multi",  # Needs further decomposition
        }
    
    async def process(
        self,
        user_input: str,
        conversation_id: str,
        context: Dict[str, Any]
    ) -> ExecutionPlan:
        """Process user input and create execution plan
        
        Args:
            user_input: Raw user input text
            conversation_id: Conversation ID for memory context
            context: Additional context (app_id, user info, etc.)
            
        Returns:
            ExecutionPlan with tasks and routing assignments
        """
        # 1. Get memory context for intent recognition
        memory_context = await self.memory.get_context_for_plan_agent(
            conversation_id,
            max_tokens=4096
        )
        history = memory_context.messages if memory_context else []
        
        # 2. Recognize intent
        intent = await self.recognize_intent(user_input, history)
        
        # 3. Decompose task
        tasks = await self.decompose_task(intent, context)
        
        # 4. Route tasks to SubAgents
        assignments = self.route_tasks(tasks)
        
        # 5. Build execution plan
        return ExecutionPlan(
            tasks=tasks,
            assignments=assignments,
            context={
                "conversation_id": conversation_id,
                "memory_context": memory_context,
                **context
            }
        )
    
    async def recognize_intent(
        self,
        user_input: str,
        history: List[Dict[str, str]]
    ) -> Intent:
        """Recognize user intent using LLM
        
        Args:
            user_input: Raw user input
            history: Conversation history
            
        Returns:
            Intent object with type, confidence, entities, parameters
        """
        prompt = self._build_intent_prompt(user_input, history)
        response = await self.llm.chat(prompt)
        
        return self._parse_intent_response(response, user_input)
    
    async def decompose_task(
        self,
        intent: Intent,
        context: Dict[str, Any]
    ) -> List[Task]:
        """Decompose intent into atomic tasks
        
        Args:
            intent: Recognized intent
            context: Execution context
            
        Returns:
            List of atomic Task objects
        """
        # Single intent -> Single task
        if intent.type != IntentType.MULTI_STEP:
            return [
                Task(
                    id=f"task_{uuid.uuid4().hex[:8]}",
                    intent_type=intent.type,
                    description=intent.raw_input,
                    parameters=intent.parameters,
                    dependencies=[],
                    priority=0
                )
            ]
        
        # Multi-step intent -> Decompose with LLM
        prompt = self._build_decompose_prompt(intent)
        response = await self.llm.chat(prompt)
        
        return self._parse_decompose_response(response)
    
    def route_tasks(self, tasks: List[Task]) -> Dict[str, str]:
        """Route tasks to appropriate SubAgents
        
        Args:
            tasks: List of tasks to route
            
        Returns:
            Dict mapping task_id to subagent_role
        """
        assignments = {}
        for task in tasks:
            role = self.routing_map.get(task.intent_type, "default")
            assignments[task.id] = role
        return assignments
    
    def _build_intent_prompt(
        self,
        user_input: str,
        history: List[Dict[str, str]]
    ) -> str:
        """Build prompt for intent recognition
        
        Args:
            user_input: User input text
            history: Conversation history
            
        Returns:
            Formatted prompt string
        """
        history_str = ""
        if history:
            history_str = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in history[-10:]  # Last 10 messages
            ])
        
        return INTENT_PROMPT_TEMPLATE.format(
            history=history_str or "无历史对话",
            user_input=user_input
        )
    
    def _build_decompose_prompt(self, intent: Intent) -> str:
        """Build prompt for task decomposition
        
        Args:
            intent: Multi-step intent to decompose
            
        Returns:
            Formatted prompt string
        """
        return DECOMPOSE_PROMPT_TEMPLATE.format(
            raw_input=intent.raw_input,
            intent_type=intent.type.value,
            parameters=json.dumps(intent.parameters, ensure_ascii=False)
        )
    
    def _parse_intent_response(
        self,
        response: str,
        raw_input: str
    ) -> Intent:
        """Parse LLM response into Intent object
        
        Args:
            response: LLM JSON response
            raw_input: Original user input
            
        Returns:
            Intent object
        """
        try:
            # Extract JSON from response
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1].strip()
            
            data = json.loads(json_str)
            
            return Intent(
                type=IntentType(data.get("intent_type", "conversation")),
                confidence=float(data.get("confidence", 0.5)),
                entities=data.get("entities", {}),
                parameters=data.get("parameters", {}),
                raw_input=raw_input
            )
        except (json.JSONDecodeError, ValueError):
            # Fallback to conversation intent on parsing failure
            return Intent(
                type=IntentType.CONVERSATION,
                confidence=0.5,
                entities={},
                parameters={},
                raw_input=raw_input
            )
    
    def _parse_decompose_response(self, response: str) -> List[Task]:
        """Parse LLM response into Task list
        
        Args:
            response: LLM JSON response
            
        Returns:
            List of Task objects
        """
        try:
            # Extract JSON from response
            json_str = response.strip()
            if json_str.startswith("```"):
                json_str = json_str.split("```")[1].strip()
            
            data = json.loads(json_str)
            
            tasks = []
            for item in data:
                task = Task(
                    id=item.get("id", f"task_{uuid.uuid4().hex[:8]}"),
                    intent_type=IntentType(item.get("intent_type", "conversation")),
                    description=item.get("description", ""),
                    parameters=item.get("parameters", {}),
                    dependencies=item.get("dependencies", []),
                    priority=item.get("priority", 0)
                )
                tasks.append(task)
            
            return tasks
        except (json.JSONDecodeError, ValueError):
            # Fallback: Return single multi-step task
            return [
                Task(
                    id=f"task_{uuid.uuid4().hex[:8]}",
                    intent_type=IntentType.MULTI_STEP,
                    description="Multi-step task",
                    parameters={},
                    dependencies=[],
                    priority=0
                )
            ]