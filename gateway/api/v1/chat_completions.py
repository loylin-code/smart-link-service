"""
OpenAI-compatible Chat Completions SSE Endpoint

POST /v1/chat/completions - Streaming chat completions
"""
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from schemas.openai_compat import (
    ChatCompletionRequest,
    StreamErrorResponse,
)
from agent.core.orchestrator import AgentOrchestrator
from core.exceptions import AgentError, LLMError


router = APIRouter(tags=["Chat Completions"])


async def stream_generator(
    orchestrator: AgentOrchestrator,
    agent_id: str,
    execution_id: str,
    request: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream from orchestrator execution.
    
    Yields:
        SSE formatted strings: "data: {...}\n\n"
    """
    try:
        # Build input_data from request
        input_data: dict[str, Any] = {}
        
        # Add messages if present
        if request.messages:
            # Extract last user message for agent execution
            user_message = None
            for msg in request.messages:
                if msg.role == "user" and msg.content:
                    user_message = msg.content
            
            if user_message:
                input_data["message"] = user_message
            
            # Add all messages for context
            input_data["messages"] = [
                {"role": msg.role, "content": msg.content or ""}
                for msg in request.messages
            ]
        
        # Add optional parameters
        if request.temperature is not None:
            input_data["temperature"] = request.temperature
        if request.max_tokens is not None:
            input_data["max_tokens"] = request.max_tokens
        if request.tools:
            input_data["tools"] = [
                {"type": t.type, "function": t.function}
                for t in request.tools
            ]
        if request.tool_choice:
            input_data["tool_choice"] = request.tool_choice
        
        # Determine include_usage from stream_options
        include_usage = False
        if request.stream_options and request.stream_options.include_usage:
            include_usage = True
        
        # Stream from orchestrator
        async for chunk in orchestrator.execute_stream_openai(
            agent_id=agent_id,
            execution_id=execution_id,
            input_data=input_data,
            include_usage=include_usage,
        ):
            # Convert chunk to SSE line
            yield chunk.to_sse_line()
        
        # Send final [DONE] marker
        yield "data: [DONE]\n\n"
        
    except AgentError as e:
        # Yield SSE error event
        error_response = StreamErrorResponse(
            error={
                "message": str(e),
                "type": "agent_error",
                "code": "agent_not_found",
            }
        )
        yield error_response.to_sse_line()
        yield "data: [DONE]\n\n"
        
    except LLMError as e:
        # Yield SSE error event for LLM errors
        error_response = StreamErrorResponse(
            error={
                "message": str(e),
                "type": "llm_error",
                "code": "llm_error",
            }
        )
        yield error_response.to_sse_line()
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        # Yield SSE error event for unexpected errors
        error_response = StreamErrorResponse(
            error={
                "message": str(e),
                "type": "internal_error",
                "code": "internal_error",
            }
        )
        yield error_response.to_sse_line()
        yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(
    data: ChatCompletionRequest,
) -> StreamingResponse:
    """
    Create chat completion with streaming response.
    
    OpenAI-compatible streaming endpoint for chat completions.
    
    Args:
        data: Chat completion request body
        
    Returns:
        StreamingResponse with SSE format
        
    Raises:
        HTTPException: If validation fails
    """
    # Validate stream mode
    if not data.stream:
        raise HTTPException(
            status_code=400,
            detail="Only streaming mode is supported. Set stream=true."
        )
    
    # Validate messages or conversation_id
    if not data.messages and not data.conversation_id:
        raise HTTPException(
            status_code=422,
            detail="Either messages or conversation_id must be provided."
        )
    
    # Extract agent_id from model field
    agent_id = data.agent_id
    
    # Generate unique execution ID
    execution_id = f"exec-{uuid.uuid4().hex[:24]}"
    
    # Create orchestrator
    orchestrator = AgentOrchestrator()
    
    # Return SSE streaming response
    return StreamingResponse(
        stream_generator(
            orchestrator=orchestrator,
            agent_id=agent_id,
            execution_id=execution_id,
            request=data,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )