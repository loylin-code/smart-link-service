"""
Unit tests for ChunkBuilder

Tests the conversion from LiteLLM format to OpenAI compatible streaming chunks.
"""
import pytest

from agent.core.chunk_builder import ChunkBuilder
from schemas.openai_compat import ChatCompletionChunk, UsageInfo


class TestBuildRoleChunk:
    """Test build_role_chunk method"""
    
    def test_build_role_chunk_returns_correct_structure(self):
        """Test that role chunk has correct structure"""
        builder = ChunkBuilder()
        chunk = builder.build_role_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4"
        )
        
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-4"
        assert chunk.object == "chat.completion.chunk"
        assert isinstance(chunk.created, int)
        assert len(chunk.choices) == 1
        assert chunk.choices[0].index == 0
        assert chunk.choices[0].delta.role == "assistant"
        assert chunk.choices[0].delta.content is None
        assert chunk.choices[0].finish_reason is None
        assert chunk.usage is None
    
    def test_build_role_chunk_different_models(self):
        """Test role chunk with different model names"""
        builder = ChunkBuilder()
        chunk = builder.build_role_chunk(
            chatcmpl_id="test-id",
            model="agent:custom-agent"
        )
        
        assert chunk.model == "agent:custom-agent"
        assert chunk.choices[0].delta.role == "assistant"


class TestBuildContentChunk:
    """Test build_content_chunk method"""
    
    def test_build_content_chunk_returns_correct_structure(self):
        """Test that content chunk has correct structure"""
        builder = ChunkBuilder()
        chunk = builder.build_content_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            content="Hello"
        )
        
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-4"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.role is None
        assert chunk.choices[0].delta.content == "Hello"
        assert chunk.choices[0].finish_reason is None
    
    def test_build_content_chunk_empty_content(self):
        """Test content chunk with empty string"""
        builder = ChunkBuilder()
        chunk = builder.build_content_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            content=""
        )
        
        assert chunk.choices[0].delta.content == ""
    
    def test_build_content_chunk_unicode_content(self):
        """Test content chunk with unicode characters"""
        builder = ChunkBuilder()
        chunk = builder.build_content_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            content="你好世界 🌍"
        )
        
        assert chunk.choices[0].delta.content == "你好世界 🌍"


class TestBuildToolCallChunk:
    """Test build_tool_call_chunk method"""
    
    def test_build_tool_call_chunk_initial(self):
        """Test initial tool call chunk with tool_call_id and name"""
        builder = ChunkBuilder()
        chunk = builder.build_tool_call_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            tool_call_index=0,
            tool_call_id="call_abc123",
            tool_name="web_search",
            tool_arguments_delta=None
        )
        
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-4"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.role is None
        assert chunk.choices[0].delta.content is None
        
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0]["index"] == 0
        assert tool_calls[0]["id"] == "call_abc123"
        assert tool_calls[0]["type"] == "function"
        assert tool_calls[0]["function"]["name"] == "web_search"
        assert tool_calls[0]["function"]["arguments"] == ""
    
    def test_build_tool_call_chunk_arguments_delta(self):
        """Test tool call chunk with arguments delta"""
        builder = ChunkBuilder()
        chunk = builder.build_tool_call_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            tool_call_index=0,
            tool_call_id=None,
            tool_name=None,
            tool_arguments_delta='{"query":'
        )
        
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0]["index"] == 0
        assert tool_calls[0]["function"]["arguments"] == '{"query":'
    
    def test_build_tool_call_chunk_multiple_indices(self):
        """Test tool call chunk with different indices"""
        builder = ChunkBuilder()
        chunk = builder.build_tool_call_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            tool_call_index=1,
            tool_call_id="call_xyz789",
            tool_name="data_analysis"
        )
        
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls[0]["index"] == 1
        assert tool_calls[0]["id"] == "call_xyz789"
        assert tool_calls[0]["function"]["name"] == "data_analysis"


class TestBuildFinalChunk:
    """Test build_final_chunk method"""
    
    def test_build_final_chunk_without_usage(self):
        """Test final chunk without usage info"""
        builder = ChunkBuilder()
        chunk = builder.build_final_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            finish_reason="stop"
        )
        
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-4"
        assert chunk.choices[0].finish_reason == "stop"
        assert chunk.choices[0].delta.role is None
        assert chunk.choices[0].delta.content is None
        assert chunk.usage is None
    
    def test_build_final_chunk_with_usage(self):
        """Test final chunk with usage info"""
        builder = ChunkBuilder()
        usage = UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        chunk = builder.build_final_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            finish_reason="tool_calls",
            usage=usage
        )
        
        assert chunk.choices[0].finish_reason == "tool_calls"
        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 100
        assert chunk.usage.completion_tokens == 50
        assert chunk.usage.total_tokens == 150
    
    def test_build_final_chunk_different_finish_reasons(self):
        """Test final chunk with different finish reasons"""
        builder = ChunkBuilder()
        
        for reason in ["stop", "tool_calls", "length", "content_filter"]:
            chunk = builder.build_final_chunk(
                chatcmpl_id="chatcmpl-123",
                model="gpt-4",
                finish_reason=reason
            )
            assert chunk.choices[0].finish_reason == reason


class TestBuildStopChunk:
    """Test build_stop_chunk method"""
    
    def test_build_stop_chunk_default_reason(self):
        """Test stop chunk with default finish reason"""
        builder = ChunkBuilder()
        chunk = builder.build_stop_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4"
        )
        
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-4"
        assert chunk.choices[0].finish_reason == "stop"
    
    def test_build_stop_chunk_custom_reason(self):
        """Test stop chunk with custom finish reason"""
        builder = ChunkBuilder()
        chunk = builder.build_stop_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            finish_reason="length"
        )
        
        assert chunk.choices[0].finish_reason == "length"


class TestBuildErrorChunk:
    """Test build_error_chunk method"""
    
    def test_build_error_chunk_returns_correct_structure(self):
        """Test error chunk structure"""
        builder = ChunkBuilder()
        chunk = builder.build_error_chunk(
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            error_message="An error occurred"
        )
        
        # Error chunk should still be a valid ChatCompletionChunk
        # but with finish_reason indicating error
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-4"
        assert chunk.choices[0].finish_reason == "content_filter"


class TestFromLiteLLMChunk:
    """Test from_litellm_chunk method"""
    
    def test_from_litellm_chunk_content_only(self):
        """Test conversion of LiteLLM chunk with content only"""
        builder = ChunkBuilder()
        accumulated_tool_calls = []
        
        litellm_chunk = {
            "content": "Hello",
            "finish_reason": None,
            "tool_calls": [],
            "usage": None
        }
        
        chunk = builder.from_litellm_chunk(
            raw_chunk=litellm_chunk,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        assert chunk.choices[0].delta.content == "Hello"
        assert chunk.choices[0].finish_reason is None
    
    def test_from_litellm_chunk_with_finish_reason(self):
        """Test conversion of LiteLLM chunk with finish reason"""
        builder = ChunkBuilder()
        accumulated_tool_calls = []
        
        litellm_chunk = {
            "content": "",
            "finish_reason": "stop",
            "tool_calls": [],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }
        
        chunk = builder.from_litellm_chunk(
            raw_chunk=litellm_chunk,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        assert chunk.choices[0].finish_reason == "stop"
        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 100
    
    def test_from_litellm_chunk_tool_call_initial(self):
        """Test conversion of LiteLLM chunk with initial tool call"""
        builder = ChunkBuilder()
        accumulated_tool_calls = []
        
        litellm_chunk = {
            "content": None,
            "finish_reason": None,
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": ""
                    }
                }
            ],
            "usage": None
        }
        
        chunk = builder.from_litellm_chunk(
            raw_chunk=litellm_chunk,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0]["index"] == 0
        assert tool_calls[0]["id"] == "call_abc123"
        assert tool_calls[0]["function"]["name"] == "web_search"
    
    def test_from_litellm_chunk_tool_call_arguments_delta(self):
        """Test conversion of LiteLLM chunk with tool call arguments delta"""
        builder = ChunkBuilder()
        accumulated_tool_calls = []
        
        # First chunk - initialize tool call
        litellm_chunk_1 = {
            "content": None,
            "finish_reason": None,
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": ""
                    }
                }
            ],
            "usage": None
        }
        
        chunk1 = builder.from_litellm_chunk(
            raw_chunk=litellm_chunk_1,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        # Second chunk - arguments delta
        litellm_chunk_2 = {
            "content": None,
            "finish_reason": None,
            "tool_calls": [
                {
                    "index": 0,
                    "function": {
                        "arguments": '{"query":"'
                    }
                }
            ],
            "usage": None
        }
        
        chunk2 = builder.from_litellm_chunk(
            raw_chunk=litellm_chunk_2,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        tool_calls = chunk2.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0]["index"] == 0
        assert tool_calls[0]["function"]["arguments"] == '{"query":"'
    
    def test_from_litellm_chunk_multiple_tool_calls(self):
        """Test conversion with multiple tool calls"""
        builder = ChunkBuilder()
        accumulated_tool_calls = []
        
        # First tool call
        litellm_chunk_1 = {
            "content": None,
            "finish_reason": None,
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_001",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": ""
                    }
                }
            ],
            "usage": None
        }
        
        builder.from_litellm_chunk(
            raw_chunk=litellm_chunk_1,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        # Second tool call
        litellm_chunk_2 = {
            "content": None,
            "finish_reason": None,
            "tool_calls": [
                {
                    "index": 1,
                    "id": "call_002",
                    "type": "function",
                    "function": {
                        "name": "analyze",
                        "arguments": ""
                    }
                }
            ],
            "usage": None
        }
        
        chunk = builder.from_litellm_chunk(
            raw_chunk=litellm_chunk_2,
            chatcmpl_id="chatcmpl-123",
            model="gpt-4",
            accumulated_tool_calls=accumulated_tool_calls
        )
        
        tool_calls = chunk.choices[0].delta.tool_calls
        assert tool_calls is not None
        assert len(tool_calls) == 1
        assert tool_calls[0]["index"] == 1
        assert tool_calls[0]["id"] == "call_002"
        assert tool_calls[0]["function"]["name"] == "analyze"
