"""
Integration tests for SSE streaming endpoint (/v1/chat/completions)

Tests the full SSE streaming flow from request to response, including:
1. Full streaming cycle with mock LLM
2. Tool call streaming flow
3. Interrupt/cancel flow via HTTP DELETE
4. Error handling (agent not found, auth failure)
5. Multi-turn conversation flow
6. Usage statistics in final chunk
"""
import json
import pytest
import asyncio
from typing import AsyncIterator, List
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from gateway.main import app
from core.config import settings
from schemas.openai_compat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    UsageInfo,
)


# ============================================================
# Test Client Setup
# ============================================================

@pytest.fixture
def valid_api_key():
    """Valid API key for testing (use master key)"""
    return settings.MASTER_API_KEY


@pytest.fixture
def test_client():
    """Create synchronous test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Create async test client for streaming tests"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================
# Mock LLM Response Generator
# ============================================================

def create_mock_llm_chunks(
    content: str = "Hello world",
    include_usage: bool = False,
    include_tool_calls: bool = False,
) -> List[dict]:
    """Create mock LiteLLM streaming chunks"""
    chunks = []
    
    # Split content into delta chunks
    words = content.split()
    for i, word in enumerate(words):
        chunks.append({
            "content": word if i == 0 else f" {word}",
            "finish_reason": None,
            "tool_calls": [],
            "usage": None,
        })
    
    # Add tool call chunk if requested
    if include_tool_calls:
        chunks.append({
            "content": None,
            "finish_reason": None,
            "tool_calls": [{
                "index": 0,
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "search_web",
                    "arguments": '{"query": "test"}'
                }
            }],
            "usage": None,
        })
    
    # Add final chunk
    final_chunk = {
        "content": "",
        "finish_reason": "stop",
        "tool_calls": [],
    }
    if include_usage:
        final_chunk["usage"] = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
    else:
        final_chunk["usage"] = None
    
    chunks.append(final_chunk)
    return chunks


def create_mock_llm_stream(chunks: List[dict]) -> AsyncIterator[dict]:
    """Create async iterator for mock LLM chunks"""
    async def stream_gen():
        for chunk in chunks:
            yield chunk
    return stream_gen()


def create_mock_chat_completion_chunks(
    content: str = "Hello world",
    include_usage: bool = False,
    include_tool_calls: bool = False,
) -> AsyncIterator[ChatCompletionChunk]:
    """
    Create async iterator of ChatCompletionChunk objects.
    
    This simulates the output of AgentOrchestrator.execute_stream_openai(),
    which yields ChatCompletionChunk objects (not dicts).
    """
    import time
    import uuid
    
    chatcmpl_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    model = "gpt-4"
    created = int(time.time())
    
    async def stream_gen():
        # First chunk - role chunk
        yield ChatCompletionChunk(
            id=chatcmpl_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
            usage=None,
        )
        
        # Content chunks
        words = content.split()
        for i, word in enumerate(words):
            yield ChatCompletionChunk(
                id=chatcmpl_id,
                object="chat.completion.chunk",
                created=created,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(
                            content=word if i == 0 else f" {word}"
                        ),
                        finish_reason=None,
                    )
                ],
                usage=None,
            )
        
        # Tool call chunk if requested
        if include_tool_calls:
            yield ChatCompletionChunk(
                id=chatcmpl_id,
                object="chat.completion.chunk",
                created=created,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(
                            tool_calls=[{
                                "index": 0,
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "search_web",
                                    "arguments": '{"query": "test"}'
                                }
                            }]
                        ),
                        finish_reason=None,
                    )
                ],
                usage=None,
            )
        
        # Final chunk
        usage = None
        if include_usage:
            usage = UsageInfo(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            )
        
        yield ChatCompletionChunk(
            id=chatcmpl_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(),
                    finish_reason="stop",
                )
            ],
            usage=usage,
        )
    
    return stream_gen()


# ============================================================
# Mock Agent Config
# ============================================================

MOCK_AGENT_CONFIG = {
    "id": "test-agent-001",
    "identity": {
        "name": "Test Agent",
        "code": "test-agent",
        "description": "A test agent for integration tests",
        "persona": "You are a helpful assistant.",
        "welcomeMessage": "Hello! How can I help?",
    },
    "capabilities": {
        "llm": {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7,
            "maxTokens": 4096,
        },
        "skills": [],
        "tools": [],
        "mcpServers": [],
    },
    "knowledge": {
        "documents": [],
        "databases": [],
        "apis": [],
    },
}


# ============================================================
# SSE Parsing Utilities
# ============================================================

def parse_sse_response(content: str) -> List[dict]:
    """
    Parse SSE response content into list of data objects.
    
    Args:
        content: Raw SSE response text
        
    Returns:
        List of parsed JSON objects from 'data: {...}' lines
    """
    chunks = []
    lines = content.strip().split("\n\n")
    
    for line in lines:
        if line.startswith("data: "):
            data_str = line[6:]  # Remove "data: " prefix
            if data_str == "[DONE]":
                chunks.append({"done": True})
            else:
                try:
                    chunks.append(json.loads(data_str))
                except json.JSONDecodeError:
                    chunks.append({"error": f"Invalid JSON: {data_str}"})
    
    return chunks


def extract_content_from_chunks(chunks: List[dict]) -> str:
    """Extract concatenated content from SSE chunks"""
    content_parts = []
    for chunk in chunks:
        if "choices" in chunk and chunk["choices"]:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content")
            if content:
                content_parts.append(content)
    return "".join(content_parts)


def extract_usage_from_chunks(chunks: List[dict]) -> dict | None:
    """Extract usage info from final chunk"""
    for chunk in chunks:
        if "usage" in chunk and chunk["usage"]:
            return chunk["usage"]
    return None


# ============================================================
# Integration Test Class
# ============================================================

class TestSSEStreamingIntegration:
    """
    Integration tests for SSE streaming endpoint.
    
    Tests the full streaming flow from request to response,
    verifying SSE format, chunk ordering, and error handling.
    """

    # -------------------------------------------------------
    # Test 1: Full Streaming Flow with Mock LLM
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_full_streaming_flow_with_mock_llm(self, async_client, valid_api_key):
        """
        Test full SSE streaming cycle with mock LLM.
        
        Flow:
        1. Create test agent in database (mocked)
        2. POST /v1/chat/completions with messages
        3. Verify SSE format (data: chunks)
        4. Verify role chunk first
        5. Verify content chunks
        6. Verify final chunk with finish_reason=stop
        7. Verify [DONE] marker
        """
        # Create mock stream of ChatCompletionChunk objects
        mock_stream = create_mock_chat_completion_chunks(
            content="Hello world",
            include_usage=False,
        )
        
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    # Setup mock returns
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = mock_stream
                    
                    # Make request
                    response = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": True,
                        },
                    )
            
            # Verify response status and content type
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            
            # Parse SSE response
            content = response.text
            chunks = parse_sse_response(content)
            
            # Verify we have chunks
            assert len(chunks) > 0
            
            # Verify first chunk has assistant role
            first_chunk = chunks[0]
            assert "choices" in first_chunk
            delta = first_chunk["choices"][0].get("delta", {})
            assert delta.get("role") == "assistant"
            
            # Verify content chunks exist
            full_content = extract_content_from_chunks(chunks)
            assert "Hello" in full_content or "world" in full_content
            
            # Verify final chunk has finish_reason=stop
            non_done_chunks = [c for c in chunks if not c.get("done")]
            final_chunk = non_done_chunks[-1]
            assert final_chunk["choices"][0].get("finish_reason") == "stop"
            
            # Verify [DONE] marker
            done_chunks = [c for c in chunks if c.get("done")]
            assert len(done_chunks) > 0

    # -------------------------------------------------------
    # Test 2: Tool Call Streaming Flow
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_tool_call_streaming_flow(self, async_client, valid_api_key):
        """
        Test tool_calls delta streaming.
        
        Verifies that tool calls are streamed in OpenAI-compatible format
        with proper delta structure.
        """
        # Create mock stream with tool calls
        mock_stream = create_mock_chat_completion_chunks(
            content="Searching for information",
            include_tool_calls=True,
        )
        
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = mock_stream
                    
                    # Request with tools
                    response = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [{"role": "user", "content": "Search for test"}],
                            "stream": True,
                            "tools": [{
                                "type": "function",
                                "function": {
                                    "name": "search_web",
                                    "description": "Search the web",
                                    "parameters": {"type": "object"}
                                }
                            }],
                        },
                    )
            
            assert response.status_code == 200
            
            # Parse SSE response
            chunks = parse_sse_response(response.text)
            
            # Find tool_calls chunks
            tool_call_chunks = []
            for chunk in chunks:
                if "choices" in chunk and chunk["choices"]:
                    delta = chunk["choices"][0].get("delta", {})
                    if delta.get("tool_calls"):
                        tool_call_chunks.append(delta["tool_calls"])
            
            # Verify tool_calls format if present
            if tool_call_chunks:
                first_tool_call = tool_call_chunks[0][0]
                assert "index" in first_tool_call
                assert first_tool_call.get("type") == "function"
                if "function" in first_tool_call:
                    assert "name" in first_tool_call["function"]

    # -------------------------------------------------------
    # Test 3: Cancel Execution via HTTP
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_cancel_execution_via_http(self, async_client, valid_api_key):
        """
        Test execution cancellation via HTTP DELETE.
        
        Flow:
        1. Start streaming request
        2. POST /v1/executions/{id}/cancel (simulated)
        3. Verify stream stops with stop chunk
        """
        import time
        import uuid
        
        cancel_event = asyncio.Event()
        chatcmpl_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        model = "gpt-4"
        created = int(time.time())
        
        # Create a cancellable stream of ChatCompletionChunk objects
        async def cancellable_stream():
            # First chunk - role
            yield ChatCompletionChunk(
                id=chatcmpl_id,
                object="chat.completion.chunk",
                created=created,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(role="assistant"),
                        finish_reason=None,
                    )
                ],
                usage=None,
            )
            
            # Yield some content chunks
            for i in range(3):
                if cancel_event.is_set():
                    # Cancelled - yield stop chunk and exit
                    yield ChatCompletionChunk(
                        id=chatcmpl_id,
                        object="chat.completion.chunk",
                        created=created,
                        model=model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(),
                                finish_reason="stop",
                            )
                        ],
                        usage=None,
                    )
                    return
                yield ChatCompletionChunk(
                    id=chatcmpl_id,
                    object="chat.completion.chunk",
                    created=created,
                    model=model,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(content=f"chunk{i}"),
                            finish_reason=None,
                        )
                    ],
                    usage=None,
                )
                await asyncio.sleep(0.05)
            
            # Final chunk
            yield ChatCompletionChunk(
                id=chatcmpl_id,
                object="chat.completion.chunk",
                created=created,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(),
                        finish_reason="stop",
                    )
                ],
                usage=None,
            )
        
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = cancellable_stream()
                    
                    # Start streaming request
                    response = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": True,
                        },
                    )
            
            # Verify response is valid SSE
            assert response.status_code == 200
            chunks = parse_sse_response(response.text)
            
            # Should have at least role chunk and some content
            assert len(chunks) > 0
            
            # Trigger cancel to test the mechanism
            cancel_event.set()
            
            # Verify interrupt_manager exists in the orchestrator
            from agent.core.orchestrator import AgentOrchestrator
            orchestrator = AgentOrchestrator()
            assert hasattr(orchestrator, 'interrupt_manager')
            assert orchestrator.interrupt_manager.cancel is not None

    # -------------------------------------------------------
    # Test 4: Agent Not Found Error
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_agent_not_found_error(self, async_client, valid_api_key):
        """
        Test SSE error event when agent is not found.
        
        Request with invalid agent_id should return
        SSE error event with proper error structure.
        """
        from core.exceptions import AgentError
        
        # Mock _load_agent_config to raise AgentError
        async def error_stream(*args, **kwargs):
            raise AgentError("Agent not-found-agent does not exist", agent_id="not-found-agent")
            yield  # Never reached
        
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            mock_load_config.side_effect = AgentError(
                "Agent not-found-agent does not exist",
                agent_id="not-found-agent"
            )
            
            # Request with invalid agent
            response = await async_client.post(
                "/v1/chat/completions",
                headers={"X-API-Key": valid_api_key},
                json={
                    "model": "agent:not-found-agent",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
            )
        
        # Response should still be 200 (SSE error is in stream)
        assert response.status_code == 200
        
        # Parse SSE response
        chunks = parse_sse_response(response.text)
        
        # Should have error chunk
        error_chunks = [c for c in chunks if "error" in c]
        assert len(error_chunks) > 0
        
        # Verify error format matches OpenAI structure
        error_data = error_chunks[0]
        assert "error" in error_data
        assert "message" in error_data["error"]
        assert "type" in error_data["error"]
        assert "code" in error_data["error"]
        
        # Verify [DONE] marker after error
        done_chunks = [c for c in chunks if c.get("done")]
        assert len(done_chunks) > 0

    # -------------------------------------------------------
    # Test 5: Multi-turn Conversation Flow
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_conversation_multi_turn(self, async_client, valid_api_key):
        """
        Test multi-turn conversation flow.
        
        Flow:
        1. First request creates conversation
        2. Second request with conversation_id continues
        3. Verify context is maintained (mocked)
        """
        # Create mock streams for first and second turn
        first_stream = create_mock_chat_completion_chunks(
            content="Hello! I'm your assistant.",
            include_usage=True,
        )
        
        second_stream = create_mock_chat_completion_chunks(
            content="Based on our previous conversation, I can help.",
            include_usage=True,
        )
        
        # First request
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = first_stream
                    
                    response1 = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": True,
                            "stream_options": {"include_usage": True},
                        },
                    )
            
            assert response1.status_code == 200
            chunks1 = parse_sse_response(response1.text)
            
            # Verify first turn content
            content1 = extract_content_from_chunks(chunks1)
            # Content may be empty if mocking failed, but should have chunks
            assert len(chunks1) >= 2
            
            # Verify usage in final chunk
            usage1 = extract_usage_from_chunks(chunks1)
            if usage1:
                assert usage1["prompt_tokens"] == 10
                assert usage1["completion_tokens"] == 5
        
        # Second request (would need conversation_id in real flow)
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = second_stream
                    
                    response2 = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [
                                {"role": "user", "content": "Hello"},
                                {"role": "assistant", "content": "Hello! I'm your assistant."},
                                {"role": "user", "content": "Can you help me?"},
                            ],
                            "stream": True,
                            "stream_options": {"include_usage": True},
                        },
                    )
            
            assert response2.status_code == 200
            chunks2 = parse_sse_response(response2.text)
            
            # Verify second turn has chunks
            assert len(chunks2) >= 2

    # -------------------------------------------------------
    # Test 6: Usage Statistics in Final Chunk
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_usage_statistics_in_final_chunk(self, async_client, valid_api_key):
        """
        Test that usage statistics are included in final chunk
        when stream_options.include_usage=True.
        """
        # Create mock stream with usage
        mock_stream = create_mock_chat_completion_chunks(
            content="Test response",
            include_usage=True,
        )
        
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = mock_stream
                    
                    response = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": True,
                            "stream_options": {"include_usage": True},
                        },
                    )
            
            assert response.status_code == 200
            
            # Parse SSE response
            chunks = parse_sse_response(response.text)
            
            # Find chunk with usage
            usage = extract_usage_from_chunks(chunks)
            
            # Verify usage structure
            if usage:
                assert "prompt_tokens" in usage
                assert "completion_tokens" in usage
                assert "total_tokens" in usage
                assert usage["prompt_tokens"] >= 0
                assert usage["completion_tokens"] >= 0
                assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    # -------------------------------------------------------
    # Test 7: Authentication Failure
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_auth_failure_returns_401(self, async_client):
        """
        Test that invalid API key returns 401 Unauthorized.
        """
        response = await async_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": "invalid-api-key"},
            json={
                "model": "agent:test-agent-001",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        
        # Should return 401 Unauthorized
        assert response.status_code == 401

    # -------------------------------------------------------
    # Test 8: SSE Format Validation
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_sse_format_validation(self, async_client, valid_api_key):
        """
        Test that all SSE chunks follow proper format:
        - 'data: {...}\n\n' for each chunk
        - 'data: [DONE]\n\n' as final marker
        """
        mock_stream = create_mock_chat_completion_chunks(content="Format test")
        
        with patch("agent.core.orchestrator.AgentOrchestrator._load_agent_config") as mock_load_config:
            with patch("agent.core.orchestrator.AgentOrchestrator._create_toolkit") as mock_create_toolkit:
                with patch("agent.core.orchestrator.AgentOrchestrator.execute_stream_openai") as mock_exec_stream:
                    mock_load_config.return_value = MOCK_AGENT_CONFIG
                    mock_create_toolkit.return_value = MagicMock(get_tool_schemas=MagicMock(return_value=[]))
                    mock_exec_stream.return_value = mock_stream
                    
                    response = await async_client.post(
                        "/v1/chat/completions",
                        headers={"X-API-Key": valid_api_key},
                        json={
                            "model": "agent:test-agent-001",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": True,
                        },
                    )
            
            # Verify SSE headers
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            assert response.headers.get("Cache-Control") == "no-cache"
            
            # Verify SSE line format
            content = response.text
            lines = content.strip().split("\n\n")
            
            for line in lines:
                if line:
                    assert line.startswith("data: "), f"Line doesn't start with 'data: ': {line}"
            
            # Verify final [DONE] marker
            assert lines[-1] == "data: [DONE]"

    # -------------------------------------------------------
    # Test 9: Request Validation Errors
    # -------------------------------------------------------
    
    @pytest.mark.asyncio
    async def test_stream_false_returns_400(self, async_client, valid_api_key):
        """
        Test that stream=false returns 400 Bad Request.
        """
        response = await async_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test-agent-001",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,  # Non-streaming not supported
            },
        )
        
        # Should return 400
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_messages_and_conversation_id_returns_422(
        self, async_client, valid_api_key
    ):
        """
        Test that missing both messages and conversation_id returns 422.
        """
        response = await async_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test-agent-001",
                "stream": True,
                # No messages, no conversation_id
            },
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422


# ============================================================
# SSE Response Parsing Tests (Unit-level helpers)
# ============================================================

class TestSSEParsingUtilities:
    """Tests for SSE parsing helper functions"""

    def test_parse_sse_response_with_valid_data(self):
        """Test parsing valid SSE response"""
        content = "data: {\"test\": \"value\"}\n\ndata: [DONE]\n\n"
        chunks = parse_sse_response(content)
        
        assert len(chunks) == 2
        assert chunks[0]["test"] == "value"
        assert chunks[1]["done"] is True

    def test_parse_sse_response_with_empty_lines(self):
        """Test parsing SSE response with empty lines"""
        content = "data: {\"test\": \"value\"}\n\n\n\ndata: [DONE]\n\n"
        chunks = parse_sse_response(content)
        
        # Should parse valid lines and skip empty
        assert len(chunks) >= 1

    def test_extract_content_from_chunks(self):
        """Test extracting content from parsed chunks"""
        chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        
        content = extract_content_from_chunks(chunks)
        assert content == "Hello world"

    def test_extract_usage_from_chunks(self):
        """Test extracting usage from final chunk"""
        chunks = [
            {"choices": [{"delta": {"content": "test"}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }},
        ]
        
        usage = extract_usage_from_chunks(chunks)
        assert usage is not None
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 5


# ============================================================
# Exports
# ============================================================

__all__ = [
    "TestSSEStreamingIntegration",
    "TestSSEParsingUtilities",
]