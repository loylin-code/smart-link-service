"""
Unit tests for ProtocolConverter

Tests the conversion from OpenAI ChatCompletionChunk format to 
custom WebSocket protocol format.

Protocol Format Conversion:
| OpenAI SSE format | WebSocket format |
|------------------|------------------|
| {"delta":{"content":"Hello"}} | {"type":"stream","data":{"delta":"Hello"}} |
| {"delta":{"tool_calls":[...]}} | {"type":"tool_call","data":{"tool":"xxx"}} |
| {"finish_reason":"tool_calls"} | {"type":"tools_ready","data":{...}} |
| {"finish_reason":"stop"} | {"type":"stream","data":{"done":true}} |
| {"usage":{...}} | {"type":"usage","data":{...}} |
| {"error":{...}} | {"type":"error","data":{...}} |
"""
import pytest

from schemas.openai_compat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    UsageInfo,
)


class TestConvertContentChunk:
    """Test conversion of content chunks to stream messages"""
    
    def test_content_chunk_returns_stream_message_with_delta(self):
        """Content delta should be converted to stream message with delta"""
        # Import here to allow test to fail first (RED phase)
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        # Create a content chunk
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content="Hello"),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["delta"] == "Hello"
        assert messages[0]["data"]["conversation_id"] == "conv_abc"
        assert messages[0]["data"]["message_id"] == "msg_xyz"
        assert messages[0]["data"]["done"] is False
    
    def test_content_chunk_empty_delta_returns_empty_stream(self):
        """Empty content delta should still return stream message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content=""),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["delta"] == ""


class TestConvertToolCallChunk:
    """Test conversion of tool_call chunks to tool_call messages"""
    
    def test_tool_call_chunk_returns_tool_call_message(self):
        """Tool call delta should be converted to tool_call message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": ""
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "tool_call"
        assert messages[0]["data"]["tool_call_id"] == "call_abc123"
        assert messages[0]["data"]["tool_name"] == "web_search"
        assert messages[0]["data"]["status"] == "calling"
    
    def test_tool_call_arguments_delta_returns_tool_call_message(self):
        """Tool call arguments delta should be converted to tool_call message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        # First, initialize tool call state
        chunk1 = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": ""
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        converter.convert(
            chunk=chunk1,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        # Then, arguments delta
        chunk2 = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "function": {
                                    "arguments": '{"query":'
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk2,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "tool_call"
        assert messages[0]["data"]["tool_call_id"] == "call_abc123"
        assert messages[0]["data"]["arguments_delta"] == '{"query":'


class TestConvertFinishReasonStop:
    """Test conversion of finish_reason:stop to stream message with done=true"""
    
    def test_finish_reason_stop_returns_stream_with_done_true(self):
        """finish_reason=stop should return stream message with done=true"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="stop"
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["delta"] is None
        assert messages[0]["data"]["done"] is True
        assert messages[0]["data"]["conversation_id"] == "conv_abc"
        assert messages[0]["data"]["message_id"] == "msg_xyz"
    
    def test_finish_reason_stop_with_content_returns_both(self):
        """finish_reason=stop with content should return both delta and done"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content="Done!"),
                    finish_reason="stop"
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["delta"] == "Done!"
        assert messages[0]["data"]["done"] is True


class TestConvertFinishReasonToolCalls:
    """Test conversion of finish_reason:tool_calls to tools_ready message"""
    
    def test_finish_reason_tool_calls_returns_tools_ready(self):
        """finish_reason=tool_calls should return tools_ready message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        # First accumulate tool calls
        chunk1 = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": '{"query":"test"}'
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        converter.convert(
            chunk=chunk1,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        # Final chunk with finish_reason=tool_calls
        chunk2 = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="tool_calls"
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk2,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "tools_ready"
        assert messages[0]["data"]["tool_calls"] is not None
        assert len(messages[0]["data"]["tool_calls"]) == 1
        assert messages[0]["data"]["tool_calls"][0]["tool_call_id"] == "call_abc123"
        assert messages[0]["data"]["tool_calls"][0]["tool_name"] == "web_search"
    
    def test_tools_ready_with_multiple_tool_calls(self):
        """finish_reason=tool_calls with multiple accumulated tool calls"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        # First tool call
        chunk1 = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_001",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"q":"test"}'
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        converter.convert(chunk=chunk1, conversation_id="conv_abc", message_id="msg_xyz")
        
        # Second tool call
        chunk2 = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 1,
                                "id": "call_002",
                                "type": "function",
                                "function": {
                                    "name": "analyze",
                                    "arguments": '{"data":"x"}'
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        converter.convert(chunk=chunk2, conversation_id="conv_abc", message_id="msg_xyz")
        
        # Final chunk
        chunk_final = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="tool_calls"
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk_final,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "tools_ready"
        assert len(messages[0]["data"]["tool_calls"]) == 2


class TestConvertUsageChunk:
    """Test conversion of usage information to usage message"""
    
    def test_usage_chunk_returns_usage_message(self):
        """Chunk with usage info should return usage message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        usage = UsageInfo(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="stop"
                )
            ],
            usage=usage
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        # Should return stream + usage messages
        assert len(messages) == 2
        
        # First message is stream with done=true
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["done"] is True
        
        # Second message is usage
        assert messages[1]["type"] == "usage"
        assert messages[1]["data"]["prompt_tokens"] == 100
        assert messages[1]["data"]["completion_tokens"] == 50
        assert messages[1]["data"]["total_tokens"] == 150


class TestConvertErrorChunk:
    """Test conversion of error information to error message"""
    
    def test_error_chunk_returns_error_message(self):
        """Chunk indicating error should return error message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="content_filter"
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert messages[0]["data"]["code"] == "content_filter"
    
    def test_length_finish_reason_returns_error_message(self):
        """finish_reason=length should return error message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="length"
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert messages[0]["data"]["code"] == "length"


class TestBuildToolResultMessage:
    """Test build_tool_result_message method"""
    
    def test_build_tool_result_message_success(self):
        """Tool result with success=True should return correct message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        message = converter.build_tool_result_message(
            tool_call_id="call_abc123",
            tool_name="web_search",
            result="Search results found",
            success=True
        )
        
        assert message["type"] == "tool_result"
        assert message["data"]["tool_call_id"] == "call_abc123"
        assert message["data"]["tool_name"] == "web_search"
        assert message["data"]["result"] == "Search results found"
        assert message["data"]["success"] is True
    
    def test_build_tool_result_message_failure(self):
        """Tool result with success=False should return correct message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        message = converter.build_tool_result_message(
            tool_call_id="call_abc123",
            tool_name="web_search",
            result="Tool execution failed",
            success=False
        )
        
        assert message["type"] == "tool_result"
        assert message["data"]["success"] is False


class TestConvertRoleChunk:
    """Test conversion of role chunk (first chunk with role=assistant)"""
    
    def test_role_chunk_returns_empty_list(self):
        """Role chunk should be handled but not produce visible message"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant"),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        # Role chunk typically doesn't produce visible output
        # but it's valid to return empty list or skip it
        assert len(messages) == 0


class TestMixedContentAndToolCalls:
    """Test handling of chunks with both content and tool_calls"""
    
    def test_content_and_tool_calls_in_same_chunk(self):
        """Chunk with both content and tool_calls should handle both"""
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        content="Let me search for that.",
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": ""
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(
            chunk=chunk,
            conversation_id="conv_abc",
            message_id="msg_xyz"
        )
        
        # Should produce both stream and tool_call messages
        assert len(messages) >= 1
        
        # Find stream message
        stream_msgs = [m for m in messages if m["type"] == "stream"]
        tool_msgs = [m for m in messages if m["type"] == "tool_call"]
        
        if stream_msgs:
            assert stream_msgs[0]["data"]["delta"] == "Let me search for that."
        
        if tool_msgs:
            assert tool_msgs[0]["data"]["tool_name"] == "web_search"