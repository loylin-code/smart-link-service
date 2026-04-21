"""
WebSocket Streaming Integration Tests

Tests the complete WebSocket flow including:
- WebSocket connection and authentication
- Chat message flow with streaming response
- Protocol conversion verification (OpenAI -> custom)
- Cancel message handling
- Tool execution flow via WebSocket
- Ping/pong handling

Note: Full WebSocket endpoint tests require proper app startup (Redis, DB).
The core functionality is tested via handler and ProtocolConverter tests.
"""
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator, Dict, Any, List

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def mock_api_key() -> str:
    """Mock API key for authentication"""
    return "sk-test-master-api-key"


@pytest.fixture
def mock_app_id() -> str:
    """Mock application ID"""
    return "app-test-001"


@pytest.fixture
def mock_client_id() -> str:
    """Mock client ID for WebSocket connection"""
    return "client-test-001"


@pytest.fixture
def mock_conversation_id() -> str:
    """Mock conversation ID"""
    return "conv-test-001"


@pytest.fixture
def mock_orchestrator_stream_chunks() -> List[Dict[str, Any]]:
    """Mock orchestrator stream chunks for testing"""
    return [
        {"type": "chunk", "content": "Hello", "done": False},
        {"type": "chunk", "content": " world", "done": False},
        {"type": "chunk", "content": "!", "done": False},
        {"type": "complete", "content": "", "done": True},
    ]


@pytest.fixture
def mock_orchestrator_tool_call_chunks() -> List[Dict[str, Any]]:
    """Mock orchestrator stream chunks with tool calls"""
    return [
        {"type": "chunk", "content": "Let me search for that.", "done": False},
        {"type": "tool_call", "tool_call_id": "call_001", "tool_name": "web_search", "arguments": '{"query":"test"}', "done": False},
        {"type": "tool_result", "tool_call_id": "call_001", "tool_name": "web_search", "result": "Search results", "success": True, "done": False},
        {"type": "chunk", "content": "Here are the results", "done": False},
        {"type": "complete", "content": "", "done": True},
    ]


@pytest.fixture
async def mock_db_session():
    """Mock database session for WebSocket handlers"""
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    return mock


@pytest.fixture
def mock_auth_context():
    """Mock authentication context for WebSocket"""
    from gateway.middleware.auth import TenantContext
    return TenantContext(
        tenant_id="tenant-001",
        user_id="user-001",
        is_master=True,
        scopes=["*"]
    )


@pytest.fixture
def minimal_ws_app():
    """Create minimal FastAPI app for WebSocket testing without full lifespan"""
    from fastapi import FastAPI, WebSocket
    from gateway.websocket.handlers import handle_ping
    from gateway.websocket.manager import manager
    
    app = FastAPI()
    
    @app.websocket("/ws/test/{client_id}")
    async def websocket_test_endpoint(websocket: WebSocket, client_id: str):
        await websocket.accept()
        await manager.connect(websocket, client_id)
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await handle_ping(client_id)
                else:
                    await websocket.send_json({"type": "echo", "data": data})
        except WebSocketDisconnect:
            manager.disconnect(client_id)
    
    return app


@pytest.fixture
def minimal_test_client(minimal_ws_app):
    """Create TestClient with minimal WebSocket app"""
    return TestClient(minimal_ws_app)


# ============================================================
# Test Class - WebSocket Handler Integration
# ============================================================

class TestWebSocketStreamingIntegration:
    """Integration tests for WebSocket streaming functionality"""
    
    # --------------------------------------------------------
    # Test 1: WebSocket Ping/Pong with Minimal App
    # --------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_websocket_ping_pong(
        self,
        mock_client_id: str,
        minimal_test_client
    ):
        """
        Test WebSocket ping/pong handling
        
        Flow:
        1. Send ping message
        2. Verify pong response
        """
        ws_url = f"/ws/test/{mock_client_id}"
        
        # Connect via WebSocket using minimal app
        with minimal_test_client.websocket_connect(ws_url) as websocket:
            # Send ping message
            ping_message = {
                "type": "ping",
                "data": {}
            }
            websocket.send_json(ping_message)
            
            # Receive pong response
            response = websocket.receive_json()
            
            # Verify pong response
            assert response.get("type") == "pong"
            assert response.get("data") == {}
            assert "timestamp" in response
    
    # --------------------------------------------------------
    # Test 2: WebSocket Chat Flow - Handler Direct Test
    # --------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_websocket_chat_handler_flow(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context,
        mock_db_session
    ):
        """
        Test WebSocket chat handler flow directly
        
        Tests handle_chat_message handler with mocked orchestrator.
        Uses execute_stream_openai with ProtocolConverter.
        """
        from gateway.websocket.handlers import handle_chat_message
        from gateway.websocket.manager import manager
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
            UsageInfo,
        )
        
        # Mock the orchestrator execute_stream_openai with proper ChatCompletionChunk objects
        async def mock_execute_stream_openai(*args, **kwargs):
            # Yield role chunk
            yield ChatCompletionChunk(
                id="chatcmpl-test",
                model="gpt-4",
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(role="assistant"),
                        finish_reason=None
                    )
                ]
            )
            # Yield content chunks
            for content in ["Hello", " world", "!"]:
                yield ChatCompletionChunk(
                    id="chatcmpl-test",
                    model="gpt-4",
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(content=content),
                            finish_reason=None
                        )
                    ]
                )
            # Yield final chunk with stop
            yield ChatCompletionChunk(
                id="chatcmpl-test",
                model="gpt-4",
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(),
                        finish_reason="stop"
                    )
                ],
                usage=UsageInfo(prompt_tokens=10, completion_tokens=3, total_tokens=13)
            )
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        sent_messages = []
        
        async def mock_send_json(msg):
            sent_messages.append(msg)
        
        mock_ws.send_json = mock_send_json
        
        # Connect client to manager
        await manager.connect(mock_ws, mock_client_id, mock_app_id)
        
        # Mock orchestrator
        with patch("gateway.websocket.handlers.AgentOrchestrator") as mock_orch_class:
            mock_orch_instance = MagicMock()
            mock_orch_instance.execute_stream_openai = mock_execute_stream_openai
            mock_orch_instance.interrupt_manager = MagicMock()
            mock_orch_instance.interrupt_manager.register = MagicMock()
            mock_orch_class.return_value = mock_orch_instance
            
            # Mock conversation service
            with patch("gateway.websocket.handlers.ConversationService") as mock_conv_service_class:
                mock_conv_service = AsyncMock()
                mock_conv_service.get_conversation = AsyncMock(return_value=MagicMock(id="conv-001"))
                mock_conv_service.create_conversation = AsyncMock(return_value=MagicMock(id="conv-002"))
                mock_conv_service.add_message = AsyncMock(return_value=MagicMock(id="msg-001"))
                mock_conv_service_class.return_value = mock_conv_service
                
                # Prepare chat message data
                chat_data = {
                    "message": "Hello, can you help me?",
                    "app_id": mock_app_id,
                    "conversation_id": None
                }
                
                # Execute handler
                await handle_chat_message(mock_client_id, chat_data, mock_db_session)
                
                # Verify messages were sent
                assert len(sent_messages) >= 2
                
                # Verify status message was sent first
                status_msg = sent_messages[0]
                assert status_msg["type"] == "status"
                assert status_msg["data"]["status"] == "processing"
                assert "execution_id" in status_msg["data"]
                
                # Verify stream messages were sent
                stream_msgs = [m for m in sent_messages if m["type"] == "stream"]
                assert len(stream_msgs) >= 1
                
                # Verify usage message was sent
                usage_msgs = [m for m in sent_messages if m["type"] == "usage"]
                assert len(usage_msgs) == 1
        
        # Cleanup
        manager.disconnect(mock_client_id)
    
    # --------------------------------------------------------
    # Test 3: WebSocket Tool Call Flow - Handler Direct Test
    # --------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_websocket_tool_call_handler_flow(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context,
        mock_db_session
    ):
        """
        Test WebSocket tool call handler flow
        
        Tests tool execution through handlers with ProtocolConverter.
        """
        from gateway.websocket.handlers import handle_tool_call
        from gateway.websocket.manager import manager
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        sent_messages = []
        
        async def mock_send_json(msg):
            sent_messages.append(msg)
        
        mock_ws.send_json = mock_send_json
        
        # Connect client to manager
        await manager.connect(mock_ws, mock_client_id, mock_app_id)
        
        # Mock skill registry - it's imported inside handle_tool_call
        mock_skill = AsyncMock()
        mock_skill.execute = AsyncMock(return_value={"result": "success"})
        
        with patch("agent.skills.base.skill_registry") as mock_registry:
            mock_registry.get = MagicMock(return_value=mock_skill)
            
            # Prepare tool call data
            tool_call_data = {
                "tool_name": "test_tool",
                "arguments": {"param": "value"}
            }
            
            # Execute handler
            await handle_tool_call(mock_client_id, tool_call_data)
            
            # Verify tool_result message was sent
            assert len(sent_messages) == 1
            result_msg = sent_messages[0]
            assert result_msg["type"] == "tool_result"
            assert result_msg["data"]["tool_name"] == "test_tool"
            assert result_msg["data"]["success"] is True
        
        # Cleanup
        manager.disconnect(mock_client_id)
    
    # --------------------------------------------------------
    # Test 4: WebSocket Cancel - InterruptManager Integration
    # --------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_websocket_cancel_interrupt_manager(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context
    ):
        """
        Test WebSocket cancel through InterruptManager
        
        Verifies cancellation mechanism works correctly.
        """
        from agent.core.interrupt_manager import InterruptManager
        
        # Create interrupt manager
        interrupt_manager = InterruptManager()
        execution_id = "exec-cancel-test"
        
        # Register execution
        interrupt_manager.register(execution_id)
        
        # Verify execution is registered by checking cancel event exists
        cancel_event = interrupt_manager.get_cancel_event(execution_id)
        assert cancel_event is not None
        
        # Request cancel - using cancel() method
        result = interrupt_manager.cancel(execution_id)
        
        # Verify cancel result
        assert result["status"] == "cancelled"
        assert "cancelled_at" in result
        
        # Verify cancel event is set (execution is cancelled)
        assert interrupt_manager.is_cancelled(execution_id)
        
        # Verify the cancel event is now set
        cancel_event = interrupt_manager.get_cancel_event(execution_id)
        assert cancel_event.is_set()
        
        # Clean up
        interrupt_manager.unregister(execution_id)
        
        # Verify execution is removed
        cancel_event = interrupt_manager.get_cancel_event(execution_id)
        assert cancel_event is None
    
    # --------------------------------------------------------
    # Test 4.5: WebSocket Cancel Handler - handle_cancel Integration
    # --------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_websocket_cancel_handler_flow(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context
    ):
        """
        Test WebSocket cancel handler flow
        
        Verifies handle_cancel handler works correctly with shared InterruptManager.
        """
        from gateway.websocket.handlers import handle_cancel, _interrupt_manager
        from gateway.websocket.manager import manager
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        sent_messages = []
        
        async def mock_send_json(msg):
            sent_messages.append(msg)
        
        mock_ws.send_json = mock_send_json
        
        # Connect client to manager
        await manager.connect(mock_ws, mock_client_id, mock_app_id)
        
        # Register an execution using the shared interrupt manager
        execution_id = "exec-handler-test"
        _interrupt_manager.register(execution_id)
        
        # Prepare cancel request data
        cancel_data = {
            "execution_id": execution_id
        }
        
        # Execute cancel handler
        await handle_cancel(mock_client_id, cancel_data)
        
        # Verify cancel_result message was sent
        assert len(sent_messages) == 1
        result_msg = sent_messages[0]
        assert result_msg["type"] == "cancel_result"
        assert result_msg["data"]["status"] == "cancelled"
        assert "cancelled_at" in result_msg["data"]
        
        # Verify execution was cancelled
        assert _interrupt_manager.is_cancelled(execution_id)
        
        # Clean up
        _interrupt_manager.unregister(execution_id)
        manager.disconnect(mock_client_id)
    
    @pytest.mark.asyncio
    async def test_websocket_cancel_handler_missing_execution_id(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context
    ):
        """
        Test WebSocket cancel handler with missing execution_id
        
        Verifies error handling when execution_id is not provided.
        """
        from gateway.websocket.handlers import handle_cancel
        from gateway.websocket.manager import manager
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        sent_messages = []
        
        async def mock_send_json(msg):
            sent_messages.append(msg)
        
        mock_ws.send_json = mock_send_json
        
        # Connect client to manager
        await manager.connect(mock_ws, mock_client_id, mock_app_id)
        
        # Prepare cancel request with missing execution_id
        cancel_data = {}
        
        # Execute cancel handler
        await handle_cancel(mock_client_id, cancel_data)
        
        # Verify error response was sent
        assert len(sent_messages) == 1
        result_msg = sent_messages[0]
        assert result_msg["type"] == "cancel_result"
        assert result_msg["data"]["status"] == "error"
        assert "message" in result_msg["data"]
        
        # Cleanup
        manager.disconnect(mock_client_id)
    
    @pytest.mark.asyncio
    async def test_websocket_cancel_handler_not_found(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context
    ):
        """
        Test WebSocket cancel handler with non-existent execution_id
        
        Verifies behavior when trying to cancel non-existent execution.
        """
        from gateway.websocket.handlers import handle_cancel
        from gateway.websocket.manager import manager
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        sent_messages = []
        
        async def mock_send_json(msg):
            sent_messages.append(msg)
        
        mock_ws.send_json = mock_send_json
        
        # Connect client to manager
        await manager.connect(mock_ws, mock_client_id, mock_app_id)
        
        # Prepare cancel request with non-existent execution_id
        cancel_data = {
            "execution_id": "non-existent-execution"
        }
        
        # Execute cancel handler
        await handle_cancel(mock_client_id, cancel_data)
        
        # Verify not_found response was sent
        assert len(sent_messages) == 1
        result_msg = sent_messages[0]
        assert result_msg["type"] == "cancel_result"
        assert result_msg["data"]["status"] == "not_found"
        
        # Cleanup
        manager.disconnect(mock_client_id)
    
    # --------------------------------------------------------
    # Test 5: WebSocket Auth - verify_api_key_ws Integration
    # --------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_websocket_auth_verification(
        self,
        mock_api_key: str,
        mock_app_id: str,
        mock_client_id: str,
        mock_auth_context,
        mock_db_session
    ):
        """
        Test WebSocket authentication verification
        
        Tests verify_api_key_ws function with mocked auth service.
        """
        from gateway.middleware.auth import verify_api_key_ws, TenantContext
        
        # Create mock WebSocket
        mock_ws = MagicMock()
        mock_ws.query_params = {"api_key": mock_api_key}
        mock_ws.headers = {}
        
        # Mock auth service
        with patch("gateway.middleware.auth.AuthService") as mock_auth_service_class:
            mock_auth_service = AsyncMock()
            mock_auth_service.validate_api_key = AsyncMock(return_value={
                "tenant_id": "tenant-001",
                "user_id": "user-001",
                "scopes": ["*"],
                "is_master": True
            })
            mock_auth_service_class.return_value = mock_auth_service
            
            # Mock database session
            with patch("gateway.middleware.auth.async_session_maker") as mock_session_maker:
                mock_session_maker.return_value.__aenter__.return_value = mock_db_session
                
                # Execute verification
                result = await verify_api_key_ws(mock_ws)
                
                # Verify result
                assert result is not None
                assert isinstance(result, TenantContext)
                assert result.tenant_id == "tenant-001"
                assert result.is_master is True


# ============================================================
# Additional ProtocolConverter Integration Tests
# ============================================================

class TestProtocolConverterIntegration:
    """Integration tests for ProtocolConverter with WebSocket flow"""
    
    @pytest.mark.asyncio
    async def test_converter_stream_chunks_integration(self):
        """
        Test ProtocolConverter integration with stream chunks
        
        Verifies OpenAI chunk -> WebSocket protocol conversion
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
            UsageInfo,
        )
        
        converter = ProtocolConverter()
        conversation_id = "conv-integration-001"
        message_id = "msg-integration-001"
        
        # Simulate a complete streaming flow
        all_messages = []
        
        # 1. Role chunk (first chunk)
        role_chunk = ChatCompletionChunk(
            id="chatcmpl-integration",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant"),
                    finish_reason=None
                )
            ]
        )
        messages = converter.convert(role_chunk, conversation_id, message_id)
        all_messages.extend(messages)
        
        # 2. Content chunks
        for content in ["Hello", " there", "!"]:
            content_chunk = ChatCompletionChunk(
                id="chatcmpl-integration",
                model="gpt-4",
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(content=content),
                        finish_reason=None
                    )
                ]
            )
            messages = converter.convert(content_chunk, conversation_id, message_id)
            all_messages.extend(messages)
        
        # 3. Final chunk with usage
        usage = UsageInfo(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15
        )
        final_chunk = ChatCompletionChunk(
            id="chatcmpl-integration",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content="How can I help?"),
                    finish_reason="stop"
                )
            ],
            usage=usage
        )
        messages = converter.convert(final_chunk, conversation_id, message_id)
        all_messages.extend(messages)
        
        # Verify conversion output
        # Filter by message type
        stream_msgs = [m for m in all_messages if m["type"] == "stream"]
        usage_msgs = [m for m in all_messages if m["type"] == "usage"]
        
        # Should have stream messages for each content + final
        assert len(stream_msgs) >= 3  # "Hello", " there", "!" or combined
        
        # Final stream message should have done=True
        final_stream = stream_msgs[-1]
        assert final_stream["data"]["done"] is True
        
        # Should have usage message
        assert len(usage_msgs) == 1
        assert usage_msgs[0]["data"]["total_tokens"] == 15
    
    @pytest.mark.asyncio
    async def test_converter_tool_call_accumulation_integration(self):
        """
        Test ProtocolConverter tool call accumulation across chunks
        
        Verifies tool_calls are properly accumulated and tools_ready is emitted
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
        )
        
        converter = ProtocolConverter()
        conversation_id = "conv-tool-001"
        message_id = "msg-tool-001"
        
        all_messages = []
        
        # 1. Tool call initialization chunk
        init_chunk = ChatCompletionChunk(
            id="chatcmpl-tool",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_search_001",
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
        messages = converter.convert(init_chunk, conversation_id, message_id)
        all_messages.extend(messages)
        
        # 2. Arguments delta chunks
        for arg_part in ['{"quer', 'y":"te', 'st"}']:
            arg_chunk = ChatCompletionChunk(
                id="chatcmpl-tool",
                model="gpt-4",
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(
                            tool_calls=[
                                {
                                    "index": 0,
                                    "function": {
                                        "arguments": arg_part
                                    }
                                }
                            ]
                        ),
                        finish_reason=None
                    )
                ]
            )
            messages = converter.convert(arg_chunk, conversation_id, message_id)
            all_messages.extend(messages)
        
        # 3. Tools ready chunk
        ready_chunk = ChatCompletionChunk(
            id="chatcmpl-tool",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="tool_calls"
                )
            ]
        )
        messages = converter.convert(ready_chunk, conversation_id, message_id)
        all_messages.extend(messages)
        
        # Verify tool call accumulation
        tool_call_msgs = [m for m in all_messages if m["type"] == "tool_call"]
        tools_ready_msgs = [m for m in all_messages if m["type"] == "tools_ready"]
        
        # Should have tool_call messages for each chunk
        assert len(tool_call_msgs) >= 4  # init + 3 argument deltas
        
        # First tool_call should have tool_call_id and tool_name
        first_tool_call = tool_call_msgs[0]
        assert first_tool_call["data"]["tool_call_id"] == "call_search_001"
        assert first_tool_call["data"]["tool_name"] == "web_search"
        
        # Should have tools_ready message
        assert len(tools_ready_msgs) == 1
        
        # tools_ready should have accumulated arguments
        tools_ready = tools_ready_msgs[0]
        assert len(tools_ready["data"]["tool_calls"]) == 1
        assert tools_ready["data"]["tool_calls"][0]["arguments"] == '{"query":"test"}'
    
    @pytest.mark.asyncio
    async def test_converter_multiple_tool_calls_integration(self):
        """
        Test ProtocolConverter handling multiple parallel tool calls
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
        )
        
        converter = ProtocolConverter()
        
        # Initialize two tool calls in same chunk
        chunk = ChatCompletionChunk(
            id="chatcmpl-multi",
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
                                    "arguments": '{"q":"a"}'
                                }
                            },
                            {
                                "index": 1,
                                "id": "call_002",
                                "type": "function",
                                "function": {
                                    "name": "analyze",
                                    "arguments": '{"d":"b"}'
                                }
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(chunk, "conv-001", "msg-001")
        
        # Both tool calls should be emitted
        assert len(messages) == 2
        
        # Verify both tool calls are tracked
        assert "call_001" in messages[0]["data"]["tool_call_id"]
        assert "search" in messages[0]["data"]["tool_name"]
        
        assert "call_002" in messages[1]["data"]["tool_call_id"]
        assert "analyze" in messages[1]["data"]["tool_name"]
        
        # Now emit tools_ready
        ready_chunk = ChatCompletionChunk(
            id="chatcmpl-multi",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="tool_calls"
                )
            ]
        )
        
        ready_messages = converter.convert(ready_chunk, "conv-001", "msg-001")
        
        # Should have tools_ready with both tool calls
        assert len(ready_messages) == 1
        assert ready_messages[0]["type"] == "tools_ready"
        assert len(ready_messages[0]["data"]["tool_calls"]) == 2
    
    @pytest.mark.asyncio
    async def test_converter_reset_between_conversations(self):
        """
        Test that ProtocolConverter.reset() clears accumulated tool calls
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
        )
        
        converter = ProtocolConverter()
        
        # Accumulate some tool calls
        chunk = ChatCompletionChunk(
            id="chatcmpl-001",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_old",
                                "type": "function",
                                "function": {"name": "old_tool", "arguments": "{}"}
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        converter.convert(chunk, "conv-001", "msg-001")
        
        # Reset for new conversation
        converter.reset()
        
        # Start new conversation
        new_chunk = ChatCompletionChunk(
            id="chatcmpl-002",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(
                        tool_calls=[
                            {
                                "index": 0,
                                "id": "call_new",
                                "type": "function",
                                "function": {"name": "new_tool", "arguments": "{}"}
                            }
                        ]
                    ),
                    finish_reason=None
                )
            ]
        )
        
        messages = converter.convert(new_chunk, "conv-002", "msg-002")
        
        # Should only have new tool call (old one was cleared)
        assert len(messages) == 1
        assert messages[0]["data"]["tool_call_id"] == "call_new"
        assert messages[0]["data"]["tool_name"] == "new_tool"
        
        # Emit tools_ready for new conversation
        ready_chunk = ChatCompletionChunk(
            id="chatcmpl-002",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="tool_calls"
                )
            ]
        )
        
        ready_messages = converter.convert(ready_chunk, "conv-002", "msg-002")
        
        # Should only have the new tool call
        assert len(ready_messages[0]["data"]["tool_calls"]) == 1
        assert ready_messages[0]["data"]["tool_calls"][0]["tool_call_id"] == "call_new"


# ============================================================
# Connection Manager Integration Tests
# ============================================================

class TestConnectionManagerIntegration:
    """Integration tests for WebSocket ConnectionManager"""
    
    @pytest.mark.asyncio
    async def test_manager_connect_disconnect(self):
        """
        Test ConnectionManager connect and disconnect flow
        """
        from gateway.websocket.manager import ConnectionManager
        
        manager = ConnectionManager()
        
        # Create mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        
        client_id = "client-manager-test"
        app_id = "app-manager-test"
        
        # Connect
        await manager.connect(mock_ws, client_id, app_id)
        
        # Verify connection is registered
        assert client_id in manager.active_connections
        assert client_id in manager.app_clients.get(app_id, set())
        
        # Send message
        test_message = {"type": "test", "data": {"value": 123}}
        await manager.send_personal_message(test_message, client_id)
        
        # Verify message was sent
        mock_ws.send_json.assert_called_once_with(test_message)
        
        # Disconnect
        manager.disconnect(client_id)
        
        # Verify connection is removed
        assert client_id not in manager.active_connections
    
    @pytest.mark.asyncio
    async def test_manager_broadcast_to_app(self):
        """
        Test ConnectionManager broadcast to app clients
        """
        from gateway.websocket.manager import ConnectionManager
        
        manager = ConnectionManager()
        
        # Create multiple mock clients for same app
        app_id = "app-broadcast-test"
        
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()
        
        # Connect both clients
        await manager.connect(mock_ws1, "client-1", app_id)
        await manager.connect(mock_ws2, "client-2", app_id)
        
        # Broadcast to app
        broadcast_msg = {"type": "broadcast", "data": {"message": "Hello all"}}
        await manager.broadcast_to_app(broadcast_msg, app_id)
        
        # Verify both clients received message
        mock_ws1.send_json.assert_called_once_with(broadcast_msg)
        mock_ws2.send_json.assert_called_once_with(broadcast_msg)
        
        # Cleanup
        manager.disconnect("client-1")
        manager.disconnect("client-2")
    
    @pytest.mark.asyncio
    async def test_manager_send_to_disconnected_client(self):
        """
        Test that sending to disconnected client handles error gracefully
        """
        from gateway.websocket.manager import ConnectionManager
        
        manager = ConnectionManager()
        
        # Send message to non-existent client
        await manager.send_personal_message(
            {"type": "test"},
            "non-existent-client"
        )
        
        # Should not raise, just log and skip


# ============================================================
# Error Handling Integration Tests
# ============================================================

class TestWebSocketErrorHandling:
    """Integration tests for WebSocket error handling"""
    
    @pytest.mark.asyncio
    async def test_error_chunk_conversion(self):
        """
        Test ProtocolConverter handles error chunks correctly
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
        )
        
        converter = ProtocolConverter()
        
        # Create error chunk with content_filter
        error_chunk = ChatCompletionChunk(
            id="chatcmpl-error",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="content_filter"
                )
            ]
        )
        
        messages = converter.convert(error_chunk, "conv-001", "msg-001")
        
        # Should produce error message
        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert messages[0]["data"]["code"] == "content_filter"
    
    @pytest.mark.asyncio
    async def test_length_limit_error_conversion(self):
        """
        Test ProtocolConverter handles length limit error
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
        )
        
        converter = ProtocolConverter()
        
        # Create length limit error chunk
        length_chunk = ChatCompletionChunk(
            id="chatcmpl-length",
            model="gpt-4",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="length"
                )
            ]
        )
        
        messages = converter.convert(length_chunk, "conv-001", "msg-001")
        
        # Should produce error message
        assert len(messages) == 1
        assert messages[0]["type"] == "error"
        assert messages[0]["data"]["code"] == "length"
    
    @pytest.mark.asyncio
    async def test_tool_result_message_building(self):
        """
        Test building tool_result message for WebSocket
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        
        converter = ProtocolConverter()
        
        # Build success result
        success_msg = converter.build_tool_result_message(
            tool_call_id="call_001",
            tool_name="web_search",
            result="Found 10 results",
            success=True
        )
        
        assert success_msg["type"] == "tool_result"
        assert success_msg["data"]["tool_call_id"] == "call_001"
        assert success_msg["data"]["tool_name"] == "web_search"
        assert success_msg["data"]["result"] == "Found 10 results"
        assert success_msg["data"]["success"] is True
        
        # Build failure result
        failure_msg = converter.build_tool_result_message(
            tool_call_id="call_002",
            tool_name="data_analysis",
            result="Error: Invalid data format",
            success=False
        )
        
        assert failure_msg["type"] == "tool_result"
        assert failure_msg["data"]["success"] is False


# ============================================================
# Full Flow Integration Test
# ============================================================

class TestWebSocketFullFlow:
    """Complete WebSocket flow integration tests"""
    
    @pytest.mark.asyncio
    async def test_complete_chat_to_stream_flow(self):
        """
        Test complete flow from chat request to stream response
        
        Simulates full WebSocket message flow without actual server
        """
        from gateway.websocket.protocol_converter import ProtocolConverter
        from gateway.websocket.manager import ConnectionManager
        from schemas.openai_compat import (
            ChatCompletionChunk,
            ChatCompletionChunkChoice,
            ChatCompletionChunkDelta,
            UsageInfo,
        )
        
        # Initialize components
        converter = ProtocolConverter()
        manager = ConnectionManager()
        
        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        sent_messages = []
        
        async def mock_send_json(msg):
            sent_messages.append(msg)
        
        mock_ws.send_json = mock_send_json
        
        # Connect client
        client_id = "client-full-flow"
        await manager.connect(mock_ws, client_id, "app-full-flow")
        
        # Simulate OpenAI streaming response
        chatcmpl_id = "chatcmpl-full-flow"
        model = "gpt-4"
        conversation_id = "conv-full-flow"
        message_id = "msg-full-flow"
        
        # 1. Role chunk
        role_chunk = ChatCompletionChunk(
            id=chatcmpl_id,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant"),
                    finish_reason=None
                )
            ]
        )
        
        for msg in converter.convert(role_chunk, conversation_id, message_id):
            await manager.send_personal_message(msg, client_id)
        
        # 2. Content chunks
        content_parts = ["Hello!", " How can I", " help you today?"]
        for content in content_parts:
            content_chunk = ChatCompletionChunk(
                id=chatcmpl_id,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(content=content),
                        finish_reason=None
                    )
                ]
            )
            
            for msg in converter.convert(content_chunk, conversation_id, message_id):
                await manager.send_personal_message(msg, client_id)
        
        # 3. Final chunk with usage
        usage = UsageInfo(
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30
        )
        
        final_chunk = ChatCompletionChunk(
            id=chatcmpl_id,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="stop"
                )
            ],
            usage=usage
        )
        
        for msg in converter.convert(final_chunk, conversation_id, message_id):
            await manager.send_personal_message(msg, client_id)
        
        # Verify all messages were sent
        assert len(sent_messages) >= 4  # 3 content + 1 final
        
        # Verify message types
        stream_msgs = [m for m in sent_messages if m["type"] == "stream"]
        usage_msgs = [m for m in sent_messages if m["type"] == "usage"]
        
        assert len(stream_msgs) >= 3
        assert len(usage_msgs) == 1
        
        # Verify last stream message has done=True
        last_stream = stream_msgs[-1]
        assert last_stream["data"]["done"] is True
        
        # Cleanup
        manager.disconnect(client_id)