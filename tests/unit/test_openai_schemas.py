"""Tests for OpenAI compatible streaming schemas"""
import pytest
import json
import time

from schemas.openai_compat import (
    ChatCompletionRequest,
    ChatMessage,
    ChatCompletionChunk,
    ChatCompletionChunkDelta,
    ChatCompletionChunkChoice,
    UsageInfo,
    StreamOptions,
    StreamErrorResponse,
    ToolDefinition,
)


class TestChatMessage:
    """Tests for ChatMessage schema"""
    
    def test_chat_message_user_role(self) -> None:
        """Test ChatMessage with user role"""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None
    
    def test_chat_message_assistant_role(self) -> None:
        """Test ChatMessage with assistant role"""
        msg = ChatMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
    
    def test_chat_message_tool_role(self) -> None:
        """Test ChatMessage with tool role"""
        msg = ChatMessage(
            role="tool",
            content="Search result: ABC",
            tool_call_id="call_123"
        )
        assert msg.role == "tool"
        assert msg.content == "Search result: ABC"
        assert msg.tool_call_id == "call_123"
    
    def test_chat_message_with_tool_calls(self) -> None:
        """Test ChatMessage with tool_calls"""
        msg = ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": '{"query": "test"}'
                    }
                }
            ]
        )
        assert msg.role == "assistant"
        assert msg.content is None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["id"] == "call_123"
    
    def test_chat_message_with_name(self) -> None:
        """Test ChatMessage with optional name field"""
        msg = ChatMessage(role="user", content="Hello", name="John")
        assert msg.name == "John"
    
    def test_chat_message_invalid_role(self) -> None:
        """Test ChatMessage rejects invalid role"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChatMessage(role="invalid", content="test")  # type: ignore[arg-type]


class TestChatCompletionRequest:
    """Tests for ChatCompletionRequest schema"""
    
    def test_minimal_request(self) -> None:
        """Test minimal valid request"""
        req = ChatCompletionRequest(model="agent:test-agent")
        assert req.model == "agent:test-agent"
        assert req.agent_id == "test-agent"
        assert req.stream is True
        assert req.messages is None
    
    def test_request_with_agent_prefix(self) -> None:
        """Test model with 'agent:' prefix extracts agent_id"""
        req = ChatCompletionRequest(model="agent:my-agent-123")
        assert req.model == "agent:my-agent-123"
        assert req.agent_id == "my-agent-123"
    
    def test_request_without_agent_prefix(self) -> None:
        """Test model without prefix uses full model as agent_id"""
        req = ChatCompletionRequest(model="custom-agent")
        assert req.model == "custom-agent"
        assert req.agent_id == "custom-agent"
    
    def test_request_with_messages(self) -> None:
        """Test request with messages list"""
        req = ChatCompletionRequest(
            model="agent:test",
            messages=[
                ChatMessage(role="user", content="Hello"),
                ChatMessage(role="assistant", content="Hi!")
            ]
        )
        assert len(req.messages) == 2  # type: ignore[arg-type]
        assert req.messages[0].role == "user"
    
    def test_request_with_conversation_id(self) -> None:
        """Test request with conversation_id for multi-turn"""
        req = ChatCompletionRequest(
            model="agent:test",
            conversation_id="conv_123"
        )
        assert req.conversation_id == "conv_123"
    
    def test_request_with_stream_options(self) -> None:
        """Test request with stream_options"""
        req = ChatCompletionRequest(
            model="agent:test",
            stream=True,
            stream_options=StreamOptions(include_usage=True)
        )
        assert req.stream is True
        assert req.stream_options is not None
        assert req.stream_options.include_usage is True
    
    def test_request_with_tools(self) -> None:
        """Test request with tools"""
        req = ChatCompletionRequest(
            model="agent:test",
            tools=[
                ToolDefinition(
                    type="function",
                    function={
                        "name": "search",
                        "description": "Search the web",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            },
                            "required": ["query"]
                        }
                    }
                )
            ]
        )
        assert len(req.tools) == 1  # type: ignore[arg-type]
        assert req.tools[0].type == "function"
        assert req.tools[0].function["name"] == "search"
    
    def test_request_with_tool_choice(self) -> None:
        """Test request with tool_choice"""
        req = ChatCompletionRequest(
            model="agent:test",
            tools=[],
            tool_choice="auto"
        )
        assert req.tool_choice == "auto"
    
    def test_request_with_temperature(self) -> None:
        """Test request with temperature"""
        req = ChatCompletionRequest(
            model="agent:test",
            temperature=0.7
        )
        assert req.temperature == 0.7
    
    def test_request_with_max_tokens(self) -> None:
        """Test request with max_tokens"""
        req = ChatCompletionRequest(
            model="agent:test",
            max_tokens=1000
        )
        assert req.max_tokens == 1000
    
    def test_request_with_top_p(self) -> None:
        """Test request with top_p"""
        req = ChatCompletionRequest(
            model="agent:test",
            top_p=0.9
        )
        assert req.top_p == 0.9
    
    def test_request_with_stop(self) -> None:
        """Test request with stop sequences"""
        req = ChatCompletionRequest(
            model="agent:test",
            stop=["\n", "END"]
        )
        assert req.stop == ["\n", "END"]
    
    def test_request_with_enable_routing(self) -> None:
        """Test request with enable_routing flag"""
        req = ChatCompletionRequest(
            model="agent:test",
            enable_routing=True
        )
        assert req.enable_routing is True
    
    def test_request_with_metadata(self) -> None:
        """Test request with metadata"""
        req = ChatCompletionRequest(
            model="agent:test",
            metadata={"user_id": "123", "session": "abc"}
        )
        assert req.metadata is not None
        assert req.metadata["user_id"] == "123"
    
    def test_request_allows_extra_fields(self) -> None:
        """Test request allows extra fields (OpenAI SDK compatibility)"""
        req = ChatCompletionRequest(
            model="agent:test",
            presence_penalty=0.5,
            frequency_penalty=0.3
        )  # type: ignore[call-arg]
        # Extra fields should be allowed due to extra="allow" config
        assert req.model == "agent:test"


class TestStreamOptions:
    """Tests for StreamOptions schema"""
    
    def test_stream_options_default(self) -> None:
        """Test StreamOptions default values"""
        opts = StreamOptions()
        assert opts.include_usage is False
    
    def test_stream_options_with_usage(self) -> None:
        """Test StreamOptions with include_usage=True"""
        opts = StreamOptions(include_usage=True)
        assert opts.include_usage is True


class TestToolDefinition:
    """Tests for ToolDefinition schema"""
    
    def test_tool_definition_default(self) -> None:
        """Test ToolDefinition default values"""
        tool = ToolDefinition(
            function={
                "name": "search",
                "description": "Search",
                "parameters": {}
            }
        )
        assert tool.type == "function"
        assert tool.function["name"] == "search"
    
    def test_tool_definition_with_full_schema(self) -> None:
        """Test ToolDefinition with complete function schema"""
        tool = ToolDefinition(
            type="function",
            function={
                "name": "web_search",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results"
                        }
                    },
                    "required": ["query"]
                }
            }
        )
        assert tool.type == "function"
        assert tool.function["name"] == "web_search"
        assert "query" in tool.function["parameters"]["properties"]


class TestUsageInfo:
    """Tests for UsageInfo schema"""
    
    def test_usage_info_creation(self) -> None:
        """Test UsageInfo creation"""
        usage = UsageInfo(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


class TestChatCompletionChunkDelta:
    """Tests for ChatCompletionChunkDelta schema"""
    
    def test_delta_with_role(self) -> None:
        """Test delta with role"""
        delta = ChatCompletionChunkDelta(role="assistant")
        assert delta.role == "assistant"
        assert delta.content is None
    
    def test_delta_with_content(self) -> None:
        """Test delta with content"""
        delta = ChatCompletionChunkDelta(content="Hello")
        assert delta.content == "Hello"
    
    def test_delta_with_tool_calls(self) -> None:
        """Test delta with tool_calls"""
        delta = ChatCompletionChunkDelta(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "search", "arguments": "{}"}
                }
            ]
        )
        assert len(delta.tool_calls) == 1  # type: ignore[arg-type]


class TestChatCompletionChunkChoice:
    """Tests for ChatCompletionChunkChoice schema"""
    
    def test_choice_default(self) -> None:
        """Test ChatCompletionChunkChoice default values"""
        choice = ChatCompletionChunkChoice(
            delta=ChatCompletionChunkDelta(content="test")
        )
        assert choice.index == 0
        assert choice.finish_reason is None
    
    def test_choice_with_finish_reason(self) -> None:
        """Test choice with finish_reason"""
        choice = ChatCompletionChunkChoice(
            delta=ChatCompletionChunkDelta(),
            finish_reason="stop"
        )
        assert choice.finish_reason == "stop"
    
    def test_choice_with_tool_calls_finish_reason(self) -> None:
        """Test choice with tool_calls finish_reason"""
        choice = ChatCompletionChunkChoice(
            delta=ChatCompletionChunkDelta(),
            finish_reason="tool_calls"
        )
        assert choice.finish_reason == "tool_calls"


class TestChatCompletionChunk:
    """Tests for ChatCompletionChunk schema"""
    
    def test_chunk_creation(self) -> None:
        """Test basic chunk creation"""
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="agent:test",
            choices=[
                ChatCompletionChunkChoice(
                    delta=ChatCompletionChunkDelta(content="Hello")
                )
            ]
        )
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "agent:test"
        assert chunk.object == "chat.completion.chunk"
        assert len(chunk.choices) == 1
    
    def test_chunk_created_timestamp(self) -> None:
        """Test chunk created field is timestamp"""
        before = int(time.time())
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="agent:test",
            choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta())]
        )
        after = int(time.time())
        assert before <= chunk.created <= after
    
    def test_chunk_with_usage(self) -> None:
        """Test chunk with usage info (final chunk)"""
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="agent:test",
            choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta())],
            usage=UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        )
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 150
    
    def test_chunk_to_sse_line(self) -> None:
        """Test to_sse_line method returns correct SSE format"""
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="agent:test",
            choices=[ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(content="test"))]
        )
        sse_line = chunk.to_sse_line()
        
        # SSE format: "data: {...}\n\n"
        assert sse_line.startswith("data: ")
        assert sse_line.endswith("\n\n")
        
        # Parse the JSON content
        json_str = sse_line[6:-2]  # Remove "data: " prefix and "\n\n" suffix
        data = json.loads(json_str)
        assert data["id"] == "chatcmpl-123"
        assert data["object"] == "chat.completion.chunk"
    
    def test_chunk_serialization(self) -> None:
        """Test chunk can be serialized to JSON"""
        chunk = ChatCompletionChunk(
            id="chatcmpl-456",
            model="agent:test",
            created=1234567890,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant", content="Hello"),
                    finish_reason=None
                )
            ],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        
        # Serialize to dict
        chunk_dict = chunk.model_dump(by_alias=True, exclude_none=True)
        assert chunk_dict["id"] == "chatcmpl-456"
        assert "object" in chunk_dict
        assert "choices" in chunk_dict
        
        # Verify JSON serializable
        json_str = json.dumps(chunk_dict)
        assert "chatcmpl-456" in json_str


class TestStreamErrorResponse:
    """Tests for StreamErrorResponse schema"""
    
    def test_error_response_creation(self) -> None:
        """Test StreamErrorResponse creation"""
        error = StreamErrorResponse(
            error={
                "message": "Invalid model",
                "type": "invalid_request_error",
                "code": "model_not_found"
            }
        )
        assert error.error["message"] == "Invalid model"
        assert error.error["type"] == "invalid_request_error"
    
    def test_error_response_to_sse_line(self) -> None:
        """Test error response to_sse_line method"""
        error = StreamErrorResponse(
            error={
                "message": "Test error",
                "type": "api_error"
            }
        )
        sse_line = error.to_sse_line()
        
        assert sse_line.startswith("data: ")
        assert sse_line.endswith("\n\n")
        
        # Parse JSON
        json_str = sse_line[6:-2]
        data = json.loads(json_str)
        assert "error" in data
        assert data["error"]["message"] == "Test error"


class TestAgentIdExtraction:
    """Tests for agent_id extraction logic from model field"""
    
    def test_extract_agent_id_with_prefix(self) -> None:
        """Test extracting agent_id from 'agent:xxx' format"""
        test_cases = [
            ("agent:test-agent", "test-agent"),
            ("agent:my-agent-123", "my-agent-123"),
            ("agent:prod/assistant", "prod/assistant"),
        ]
        
        for model, expected in test_cases:
            req = ChatCompletionRequest(model=model)
            assert req.agent_id == expected, f"Failed for model={model}"
    
    def test_extract_agent_id_without_prefix(self) -> None:
        """Test using full model as agent_id when no prefix"""
        test_cases = [
            ("custom-agent", "custom-agent"),
            ("gpt-4", "gpt-4"),
            ("my_agent", "my_agent"),
        ]
        
        for model, expected in test_cases:
            req = ChatCompletionRequest(model=model)
            assert req.agent_id == expected, f"Failed for model={model}"
    
    def test_extract_agent_id_edge_cases(self) -> None:
        """Test edge cases for agent_id extraction"""
        # Empty after prefix
        req = ChatCompletionRequest(model="agent:")
        assert req.agent_id == ""
        
        # Just prefix
        req = ChatCompletionRequest(model="agent")
        assert req.agent_id == "agent"
        
        # Multiple colons
        req = ChatCompletionRequest(model="agent:namespace:agent-id")
        assert req.agent_id == "namespace:agent-id"
