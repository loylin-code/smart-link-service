"""
LLMClient chat_stream_openai method tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from agent.llm.client import LLMClient


class TestChatStreamOpenaiBasic:
    """Test basic chat_stream_openai functionality"""

    @pytest.mark.asyncio
    async def test_returns_content_chunks(self):
        """Should yield content chunks in OpenAI format"""
        client = LLMClient()
        
        # Mock LiteLLM streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices[0].delta.content = "Hello"
        mock_chunk1.choices[0].delta.tool_calls = None
        mock_chunk1.choices[0].finish_reason = None
        
        mock_chunk2 = MagicMock()
        mock_chunk2.choices[0].delta.content = " world"
        mock_chunk2.choices[0].delta.tool_calls = None
        mock_chunk2.choices[0].finish_reason = None
        
        mock_chunk3 = MagicMock()
        mock_chunk3.choices[0].delta.content = ""
        mock_chunk3.choices[0].delta.tool_calls = None
        mock_chunk3.choices[0].finish_reason = "stop"
        mock_chunk3.usage = MagicMock()
        mock_chunk3.usage.prompt_tokens = 10
        mock_chunk3.usage.completion_tokens = 5
        mock_chunk3.usage.total_tokens = 15
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk1, mock_chunk2, mock_chunk3]
        
        messages = [{"role": "user", "content": "Hi"}]
        
        chunks = []
        with patch('agent.llm.client.acompletion', return_value=mock_stream):
            async for chunk in client.chat_stream_openai(messages):
                chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) == 3
        assert chunks[0]["content"] == "Hello"
        assert chunks[1]["content"] == " world"
        assert chunks[2]["content"] == ""
        assert chunks[2]["finish_reason"] == "stop"
        assert chunks[2]["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }

    @pytest.mark.asyncio
    async def test_tool_calls_format_conversion(self):
        """Should convert LiteLLM tool_calls to OpenAI format"""
        client = LLMClient()
        
        # Mock tool call chunk
        mock_tool_call = MagicMock()
        mock_tool_call.index = 0
        mock_tool_call.id = "call_abc123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "search"
        mock_tool_call.function.arguments = '{"query": "test"}'
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = None
        mock_chunk.choices[0].delta.tool_calls = [mock_tool_call]
        mock_chunk.choices[0].finish_reason = None
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Search for test"}]
        tools = [{"type": "function", "function": {"name": "search"}}]
        
        chunks = []
        with patch('agent.llm.client.acompletion', return_value=mock_stream):
            async for chunk in client.chat_stream_openai(messages, tools=tools):
                chunks.append(chunk)
        
        # Verify tool_calls format
        assert len(chunks) == 1
        assert "tool_calls" in chunks[0]
        assert len(chunks[0]["tool_calls"]) == 1
        tool_call = chunks[0]["tool_calls"][0]
        assert tool_call["index"] == 0
        assert tool_call["id"] == "call_abc123"
        assert tool_call["type"] == "function"
        assert tool_call["function"]["name"] == "search"
        assert tool_call["function"]["arguments"] == '{"query": "test"}'

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_chunk(self):
        """Should handle multiple tool_calls in single chunk"""
        client = LLMClient()
        
        # Mock two tool calls
        mock_tool_call1 = MagicMock()
        mock_tool_call1.index = 0
        mock_tool_call1.id = "call_1"
        mock_tool_call1.type = "function"
        mock_tool_call1.function.name = "tool1"
        mock_tool_call1.function.arguments = '{"arg": "1"}'
        
        mock_tool_call2 = MagicMock()
        mock_tool_call2.index = 1
        mock_tool_call2.id = "call_2"
        mock_tool_call2.type = "function"
        mock_tool_call2.function.name = "tool2"
        mock_tool_call2.function.arguments = '{"arg": "2"}'
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = None
        mock_chunk.choices[0].delta.tool_calls = [mock_tool_call1, mock_tool_call2]
        mock_chunk.choices[0].finish_reason = None
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Call tools"}]
        
        chunks = []
        with patch('agent.llm.client.acompletion', return_value=mock_stream):
            async for chunk in client.chat_stream_openai(messages, tools=[]):
                chunks.append(chunk)
        
        assert len(chunks) == 1
        assert len(chunks[0]["tool_calls"]) == 2


class TestChatStreamOpenaiParameters:
    """Test chat_stream_openai parameter handling"""

    @pytest.mark.asyncio
    async def test_stream_options_include_usage(self):
        """Should pass stream_options to LiteLLM when include_usage=True"""
        client = LLMClient()
        
        # Mock response
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = "test"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Hi"}]
        stream_options = {"include_usage": True}
        
        mock_acompletion = AsyncMock(return_value=mock_stream)
        
        with patch('agent.llm.client.acompletion', mock_acompletion):
            async for _ in client.chat_stream_openai(messages, stream_options=stream_options):
                pass
        
        # Verify stream_options passed
        call_args = mock_acompletion.call_args
        assert call_args is not None
        assert call_args.kwargs.get("stream_options") == stream_options

    @pytest.mark.asyncio
    async def test_default_parameters(self):
        """Should use default parameters"""
        client = LLMClient()
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = "test"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Hi"}]
        
        mock_acompletion = AsyncMock(return_value=mock_stream)
        
        with patch('agent.llm.client.acompletion', mock_acompletion):
            async for _ in client.chat_stream_openai(messages):
                pass
        
        # Verify default parameters
        call_args = mock_acompletion.call_args
        assert call_args.kwargs["temperature"] == 0.7
        assert call_args.kwargs["max_tokens"] == 4096
        assert call_args.kwargs["stream"] is True

    @pytest.mark.asyncio
    async def test_custom_parameters(self):
        """Should use custom parameters"""
        client = LLMClient()
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = "test"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Hi"}]
        
        mock_acompletion = AsyncMock(return_value=mock_stream)
        
        with patch('agent.llm.client.acompletion', mock_acompletion):
            async for _ in client.chat_stream_openai(
                messages,
                temperature=0.5,
                max_tokens=2048
            ):
                pass
        
        # Verify custom parameters
        call_args = mock_acompletion.call_args
        assert call_args.kwargs["temperature"] == 0.5
        assert call_args.kwargs["max_tokens"] == 2048


class TestChatStreamOpenaiTools:
    """Test chat_stream_openai with tools"""

    @pytest.mark.asyncio
    async def test_tools_passed_to_litellm(self):
        """Should pass tools to LiteLLM request"""
        client = LLMClient()
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = "test"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Use tool"}]
        tools = [{"type": "function", "function": {"name": "my_tool"}}]
        
        mock_acompletion = AsyncMock(return_value=mock_stream)
        
        with patch('agent.llm.client.acompletion', mock_acompletion):
            async for _ in client.chat_stream_openai(messages, tools=tools):
                pass
        
        # Verify tools passed
        call_args = mock_acompletion.call_args
        assert call_args.kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_tool_choice_passed_to_litellm(self):
        """Should pass tool_choice to LiteLLM request"""
        client = LLMClient()
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = "test"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Use tool"}]
        tools = [{"type": "function", "function": {"name": "my_tool"}}]
        
        mock_acompletion = AsyncMock(return_value=mock_stream)
        
        with patch('agent.llm.client.acompletion', mock_acompletion):
            async for _ in client.chat_stream_openai(
                messages,
                tools=tools,
                tool_choice="required"
            ):
                pass
        
        # Verify tool_choice passed
        call_args = mock_acompletion.call_args
        assert call_args.kwargs["tool_choice"] == "required"


class TestChatStreamOpenaiUsage:
    """Test usage handling in chat_stream_openai"""

    @pytest.mark.asyncio
    async def test_usage_only_in_last_chunk(self):
        """Should only include usage in final chunk"""
        client = LLMClient()
        
        # First chunk - no usage
        mock_chunk1 = MagicMock(spec=['choices'])
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta = MagicMock()
        mock_chunk1.choices[0].delta.content = "Hello"
        mock_chunk1.choices[0].delta.tool_calls = None
        mock_chunk1.choices[0].finish_reason = None
        # No usage attribute
        
        # Last chunk - has usage
        mock_chunk2 = MagicMock()
        mock_chunk2.choices[0].delta.content = ""
        mock_chunk2.choices[0].delta.tool_calls = None
        mock_chunk2.choices[0].finish_reason = "stop"
        mock_chunk2.usage = MagicMock()
        mock_chunk2.usage.prompt_tokens = 10
        mock_chunk2.usage.completion_tokens = 5
        mock_chunk2.usage.total_tokens = 15
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk1, mock_chunk2]
        
        messages = [{"role": "user", "content": "Hi"}]
        
        chunks = []
        with patch('agent.llm.client.acompletion', return_value=mock_stream):
            async for chunk in client.chat_stream_openai(messages):
                chunks.append(chunk)
        
        # First chunk should not have usage
        assert "usage" not in chunks[0] or chunks[0].get("usage") is None
        
        # Last chunk should have usage
        assert "usage" in chunks[1]
        assert chunks[1]["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }

    @pytest.mark.asyncio
    async def test_no_usage_when_not_provided(self):
        """Should handle response without usage info"""
        client = LLMClient()
        
        mock_chunk = MagicMock()
        mock_chunk.choices[0].delta.content = "test"
        mock_chunk.choices[0].delta.tool_calls = None
        mock_chunk.choices[0].finish_reason = "stop"
        # No usage attribute
        del mock_chunk.usage
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_chunk]
        
        messages = [{"role": "user", "content": "Hi"}]
        
        chunks = []
        with patch('agent.llm.client.acompletion', return_value=mock_stream):
            async for chunk in client.chat_stream_openai(messages):
                chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].get("usage") is None
