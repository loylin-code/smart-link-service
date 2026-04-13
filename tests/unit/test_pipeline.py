"""PipelineManager 单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestPipelineManager:
    """PipelineManager 测试类"""
    
    @pytest.mark.asyncio
    async def test_execute_single_agent(self):
        """测试单 Agent 执行"""
        from agent.agentscope.pipeline import PipelineManager, PipelineType
        
        mock_agent = AsyncMock()
        mock_agent.return_value = MagicMock(content="response")
        
        manager = PipelineManager()
        result = await manager.execute(
            agents=[mock_agent],
            input_msg=MagicMock(),
            pipeline_type=PipelineType.SINGLE
        )
        
        assert result is not None
        mock_agent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_sequential_pipeline(self):
        """测试顺序管道执行 A -> B -> C"""
        from agent.agentscope.pipeline import PipelineManager, PipelineType
        
        mock_agent_a = AsyncMock()
        mock_agent_b = AsyncMock()
        mock_agent_c = AsyncMock()
        
        msg = MagicMock()
        mock_agent_a.return_value = MagicMock(content="A response")
        mock_agent_b.return_value = MagicMock(content="B response")
        mock_agent_c.return_value = MagicMock(content="C response")
        
        manager = PipelineManager()
        result = await manager.execute(
            agents=[mock_agent_a, mock_agent_b, mock_agent_c],
            input_msg=msg,
            pipeline_type=PipelineType.SEQUENTIAL
        )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_execute_parallel_pipeline(self):
        """测试并行管道执行"""
        from agent.agentscope.pipeline import PipelineManager, PipelineType
        
        mock_agent_1 = AsyncMock()
        mock_agent_2 = AsyncMock()
        mock_agent_3 = AsyncMock()
        
        msg = MagicMock()
        mock_agent_1.return_value = MagicMock(content="response 1")
        mock_agent_2.return_value = MagicMock(content="response 2")
        mock_agent_3.return_value = MagicMock(content="response 3")
        
        manager = PipelineManager()
        result = await manager.execute(
            agents=[mock_agent_1, mock_agent_2, mock_agent_3],
            input_msg=msg,
            pipeline_type=PipelineType.PARALLEL
        )
        
        assert result is not None
    
    def test_pipeline_type_enum(self):
        """测试 PipelineType 枚举值"""
        from agent.agentscope.pipeline import PipelineType
        
        assert PipelineType.SINGLE.value == "single"
        assert PipelineType.SEQUENTIAL.value == "sequential"
        assert PipelineType.PARALLEL.value == "parallel"
