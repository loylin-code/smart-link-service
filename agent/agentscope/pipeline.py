"""PipelineManager for multi-agent workflow orchestration"""
from enum import Enum
from typing import Union, List
from agentscope.message import Msg
from agentscope.pipeline import SequentialPipeline, FanoutPipeline


class PipelineType(str, Enum):
    """管道类型枚举"""
    SINGLE = "single"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class PipelineManager:
    """多 Agent 工作流编排管理器"""
    
    async def execute(
        self,
        agents: List,
        input_msg: Msg,
        pipeline_type: PipelineType
    ) -> Union[Msg, List[Msg]]:
        """
        执行 Agent 管道
        
        Args:
            agents: Agent 列表
            input_msg: 输入消息
            pipeline_type: 管道类型
            
        Returns:
            单个或多个消息响应
        """
        if pipeline_type == PipelineType.SINGLE:
            return await agents[0](input_msg)
        
        elif pipeline_type == PipelineType.SEQUENTIAL:
            pipeline = SequentialPipeline(agents=agents)
            return await pipeline(input_msg)
        
        elif pipeline_type == PipelineType.PARALLEL:
            pipeline = FanoutPipeline(agents=agents, enable_gather=True)
            return await pipeline(input_msg)
        
        raise ValueError(f"Unknown pipeline type: {pipeline_type}")
    
    async def execute_stream(
        self,
        agents: List,
        input_msg: Msg,
        pipeline_type: PipelineType
    ):
        """
        流式执行 Agent 管道
        
        Args:
            agents: Agent 列表
            input_msg: 输入消息
            pipeline_type: 管道类型
            
        Yields:
            响应块
        """
        if pipeline_type == PipelineType.SINGLE:
            result = await agents[0](input_msg)
            yield result
        
        elif pipeline_type == PipelineType.SEQUENTIAL:
            pipeline = SequentialPipeline(agents=agents)
            result = await pipeline(input_msg)
            yield result
        
        elif pipeline_type == PipelineType.PARALLEL:
            pipeline = FanoutPipeline(agents=agents, enable_gather=True)
            result = await pipeline(input_msg)
            yield result
        
        else:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")
