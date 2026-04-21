"""
OpenAI Chat Completions API Compatible Schemas

Compatible with OpenAI SDK streaming interface.
Supports:
- Chat completions with streaming (SSE)
- Tool calling
- Multi-turn conversations via conversation_id
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def get_utc8_timestamp() -> int:
    """
    Get Unix timestamp in UTC+8 (China Standard Time)
    
    Returns:
        Unix timestamp adjusted for UTC+8 timezone
    """
    # UTC+8 is 8 hours ahead of UTC
    utc8 = timezone(timedelta(hours=8))
    now_utc8 = datetime.now(utc8)
    return int(now_utc8.timestamp())


# ============================================================
# Stream Options
# ============================================================

class StreamOptions(BaseModel):
    """Stream options for controlling streaming behavior"""
    include_usage: bool = Field(
        default=False,
        description="Include usage statistics in final chunk"
    )


# ============================================================
# Tool Definition
# ============================================================

class ToolDefinition(BaseModel):
    """Tool definition for function calling"""
    model_config = ConfigDict(protected_namespaces=())
    
    type: Literal["function"] = Field(default="function")
    function: Dict[str, Any] = Field(
        ...,
        description="Function definition with name, description, parameters"
    )


# ============================================================
# Message Schema
# ============================================================

class ChatMessage(BaseModel):
    """Chat message following OpenAI format"""
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ...,
        description="Message role"
    )
    content: Optional[str] = Field(default=None, description="Message content")
    name: Optional[str] = Field(default=None, description="Optional name for user/assistant")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Tool calls (for assistant role)"
    )
    tool_call_id: Optional[str] = Field(
        default=None,
        description="Tool call ID (for tool role)"
    )


# ============================================================
# Request Schema
# ============================================================

class ChatCompletionRequest(BaseModel):
    """
    Chat completion request compatible with OpenAI SDK
    
    Example:
        - model: "agent:my-agent" → agent_id = "my-agent"
        - model: "custom-agent" → agent_id = "custom-agent"
    """
    model_config = ConfigDict(extra="allow")  # Allow extra fields for SDK compatibility
    
    model: str = Field(..., description="Model ID in format 'agent:xxx' or 'xxx'")
    messages: Optional[List[ChatMessage]] = Field(default=None)
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation ID for multi-turn (alternative to messages)"
    )
    stream: bool = Field(default=True, description="Enable streaming response")
    stream_options: Optional[StreamOptions] = Field(default=None)
    tools: Optional[List[ToolDefinition]] = Field(default=None)
    tool_choice: Optional[Literal["auto", "none", "required"]] = Field(
        default=None,
        description="Tool choice strategy"
    )
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop: Optional[List[str]] = Field(default=None)
    enable_routing: bool = Field(default=False, description="Enable intelligent routing")
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    
    @property
    def agent_id(self) -> str:
        """
        Extract agent_id from model field
        
        - "agent:xxx" → "xxx"
        - "xxx" → "xxx"
        """
        if self.model.startswith("agent:"):
            return self.model[6:]
        return self.model


# ============================================================
# Usage Info
# ============================================================

class UsageInfo(BaseModel):
    """Token usage statistics"""
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    completion_tokens: int = Field(..., description="Number of completion tokens")
    total_tokens: int = Field(..., description="Total tokens used")


# ============================================================
# Chunk Delta
# ============================================================

class ChatCompletionChunkDelta(BaseModel):
    """Delta content in streaming chunk"""
    role: Optional[Literal["assistant"]] = Field(default=None)
    content: Optional[str] = Field(default=None)
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None)


# ============================================================
# Chunk Choice
# ============================================================

class ChatCompletionChunkChoice(BaseModel):
    """Choice in streaming chunk"""
    index: int = Field(default=0)
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[Literal["stop", "tool_calls", "length", "content_filter"]] = Field(
        default=None
    )


# ============================================================
# Streaming Chunk
# ============================================================

class ChatCompletionChunk(BaseModel):
    """
    Streaming chunk for chat completion
    
    SSE format: data: {...}\n\n
    """
    id: str = Field(..., description="Chunk ID")
    object: Literal["chat.completion.chunk"] = Field(default="chat.completion.chunk")
    created: int = Field(default_factory=get_utc8_timestamp, description="Unix timestamp (UTC+8)")
    model: str = Field(..., description="Model ID")
    choices: List[ChatCompletionChunkChoice]
    usage: Optional[UsageInfo] = Field(default=None)
    
    def to_sse_line(self) -> str:
        """
        Convert chunk to SSE (Server-Sent Events) line format
        
        Returns:
            String in format "data: {json}\n\n"
        """
        data = self.model_dump(by_alias=True, exclude_none=True)
        return f"data: {json.dumps(data)}\n\n"


# ============================================================
# Error Response
# ============================================================

class StreamErrorResponse(BaseModel):
    """
    Streaming error response
    
    OpenAI error format:
    {
        "error": {
            "message": "...",
            "type": "...",
            "code": "..."
        }
    }
    """
    error: Dict[str, Any] = Field(..., description="Error object with message, type, code")
    
    def to_sse_line(self) -> str:
        """
        Convert error to SSE line format
        
        Returns:
            String in format "data: {json}\n\n"
        """
        data = self.model_dump(by_alias=True, exclude_none=True)
        return f"data: {json.dumps(data)}\n\n"


# ============================================================
# Exports
# ============================================================

__all__ = [
    # Utility
    "get_utc8_timestamp",
    # Request
    "ChatCompletionRequest",
    "ChatMessage",
    "StreamOptions",
    "ToolDefinition",
    # Response
    "ChatCompletionChunk",
    "ChatCompletionChunkDelta",
    "ChatCompletionChunkChoice",
    "UsageInfo",
    # Error
    "StreamErrorResponse",
]
