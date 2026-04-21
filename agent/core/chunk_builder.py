"""
ChunkBuilder - Convert LiteLLM chunks to OpenAI compatible format

Builds streaming chunks for OpenAI Chat Completions API compatibility.
"""
from typing import Any, Literal

from schemas.openai_compat import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    UsageInfo,
    get_utc8_timestamp,
)

FinishReason = Literal["stop", "tool_calls", "length", "content_filter"]


class ChunkBuilder:
    """
    Builder for OpenAI compatible streaming chunks.
    
    Converts LiteLLM raw chunks to OpenAI ChatCompletionChunk format.
    Supports:
    - Role chunks (initial assistant role)
    - Content chunks (text deltas)
    - Tool call chunks (function calling)
    - Final chunks (with finish reason and usage)
    - Error chunks
    """
    
    def __init__(self):
        """Initialize ChunkBuilder"""
        pass
    
    def _create_base_chunk(
        self,
        chatcmpl_id: str,
        model: str,
    ) -> ChatCompletionChunk:
        """
        Create base chunk structure with common fields.
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            
        Returns:
            ChatCompletionChunk with base fields populated
        """
        return ChatCompletionChunk(
            id=chatcmpl_id,
            object="chat.completion.chunk",
            created=get_utc8_timestamp(),
            model=model,
            choices=[],
            usage=None,
        )
    
    def _create_choice(
        self,
        delta: ChatCompletionChunkDelta,
        finish_reason: FinishReason | None = None,
        index: int = 0,
    ) -> ChatCompletionChunkChoice:
        """
        Create a choice with delta and optional finish reason.
        
        Args:
            delta: Delta content
            finish_reason: Optional finish reason
            index: Choice index
            
        Returns:
            ChatCompletionChunkChoice
        """
        return ChatCompletionChunkChoice(
            index=index,
            delta=delta,
            finish_reason=finish_reason,
        )
    
    def build_role_chunk(
        self,
        chatcmpl_id: str,
        model: str,
    ) -> ChatCompletionChunk:
        """
        Build initial chunk with assistant role.
        
        This is the first chunk in a streaming response, establishing
        the assistant role before content deltas.
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            
        Returns:
            ChatCompletionChunk with role:assistant
        """
        chunk = self._create_base_chunk(chatcmpl_id, model)
        
        delta = ChatCompletionChunkDelta(
            role="assistant",
            content=None,
            tool_calls=None,
        )
        
        choice = self._create_choice(delta=delta, finish_reason=None)
        chunk.choices = [choice]
        
        return chunk
    
    def build_content_chunk(
        self,
        chatcmpl_id: str,
        model: str,
        content: str,
    ) -> ChatCompletionChunk:
        """
        Build chunk with content delta.
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            content: Content text delta
            
        Returns:
            ChatCompletionChunk with content delta
        """
        chunk = self._create_base_chunk(chatcmpl_id, model)
        
        delta = ChatCompletionChunkDelta(
            role=None,
            content=content,
            tool_calls=None,
        )
        
        choice = self._create_choice(delta=delta, finish_reason=None)
        chunk.choices = [choice]
        
        return chunk
    
    def build_tool_call_chunk(
        self,
        chatcmpl_id: str,
        model: str,
        tool_call_index: int,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_arguments_delta: str | None = None,
    ) -> ChatCompletionChunk:
        """
        Build chunk with tool call delta.
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            tool_call_index: Index of the tool call (0-based)
            tool_call_id: Tool call ID (required for initial chunk)
            tool_name: Function name (required for initial chunk)
            tool_arguments_delta: Arguments JSON delta
            
        Returns:
            ChatCompletionChunk with tool_calls delta
        """
        chunk = self._create_base_chunk(chatcmpl_id, model)
        
        # Build tool call dict
        tool_call: dict[str, Any] = {
            "index": tool_call_index,
        }
        
        if tool_call_id is not None:
            tool_call["id"] = tool_call_id
        
        if tool_name is not None:
            tool_call["type"] = "function"
            tool_call["function"] = {
                "name": tool_name,
                "arguments": tool_arguments_delta if tool_arguments_delta is not None else "",
            }
        elif tool_arguments_delta is not None:
            # Arguments-only delta (subsequent chunk)
            tool_call["function"] = {
                "arguments": tool_arguments_delta,
            }
        
        delta = ChatCompletionChunkDelta(
            role=None,
            content=None,
            tool_calls=[tool_call],
        )
        
        choice = self._create_choice(delta=delta, finish_reason=None)
        chunk.choices = [choice]
        
        return chunk
    
    def build_final_chunk(
        self,
        chatcmpl_id: str,
        model: str,
        finish_reason: FinishReason,
        usage: UsageInfo | None = None,
    ) -> ChatCompletionChunk:
        """
        Build final chunk with finish reason.
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            finish_reason: Finish reason (stop, tool_calls, length, content_filter)
            usage: Optional usage statistics
            
        Returns:
            ChatCompletionChunk with finish_reason
        """
        chunk = self._create_base_chunk(chatcmpl_id, model)
        
        delta = ChatCompletionChunkDelta(
            role=None,
            content=None,
            tool_calls=None,
        )
        
        choice = self._create_choice(delta=delta, finish_reason=finish_reason)
        chunk.choices = [choice]
        chunk.usage = usage
        
        return chunk
    
    def build_stop_chunk(
        self,
        chatcmpl_id: str,
        model: str,
        finish_reason: FinishReason = "stop",
    ) -> ChatCompletionChunk:
        """
        Build stop chunk (for interrupted streams).
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            finish_reason: Finish reason (default: "stop")
            
        Returns:
            ChatCompletionChunk with stop finish_reason
        """
        return self.build_final_chunk(
            chatcmpl_id=chatcmpl_id,
            model=model,
            finish_reason=finish_reason,
            usage=None,
        )
    
    def build_error_chunk(
        self,
        chatcmpl_id: str,
        model: str,
        error_message: str,
    ) -> ChatCompletionChunk:
        """
        Build error chunk.
        
        Args:
            chatcmpl_id: Chunk ID
            model: Model identifier
            error_message: Error message
            
        Returns:
            ChatCompletionChunk with error indication
        """
        # Use content_filter as finish_reason to indicate error
        return self.build_final_chunk(
            chatcmpl_id=chatcmpl_id,
            model=model,
            finish_reason="content_filter",
            usage=None,
        )
    
    def from_litellm_chunk(
        self,
        raw_chunk: dict[str, Any],
        chatcmpl_id: str,
        model: str,
        accumulated_tool_calls: list[dict[str, Any]],
    ) -> ChatCompletionChunk:
        """
        Convert LiteLLM chunk to OpenAI compatible format.
        
        LiteLLM format:
        {
            "content": str | None,
            "finish_reason": str | None,
            "tool_calls": list[dict] | [],
            "usage": dict | None
        }
        
        Args:
            raw_chunk: Raw LiteLLM chunk dict
            chatcmpl_id: Chunk ID
            model: Model identifier
            accumulated_tool_calls: Accumulator for tool call state
            
        Returns:
            ChatCompletionChunk in OpenAI format
        """
        chunk = self._create_base_chunk(chatcmpl_id, model)
        
        # Extract fields from LiteLLM chunk
        content = raw_chunk.get("content")
        finish_reason_raw = raw_chunk.get("finish_reason")
        tool_calls_raw = raw_chunk.get("tool_calls", [])
        usage_raw = raw_chunk.get("usage")
        
        # Validate and cast finish_reason
        finish_reason: FinishReason | None = None
        if finish_reason_raw in ["stop", "tool_calls", "length", "content_filter"]:
            finish_reason = finish_reason_raw  # type: ignore[assignment]
        
        # Parse usage if present
        usage: UsageInfo | None = None
        if usage_raw is not None:
            usage = UsageInfo(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            )
        
        # Build tool_calls for delta
        tool_calls_delta: list[dict[str, Any]] | None = None
        
        if tool_calls_raw:
            tool_calls_delta = []
            
            for tc_raw in tool_calls_raw:
                index = tc_raw.get("index", 0)
                
                # Build tool call entry
                tool_call_entry: dict[str, Any] = {
                    "index": index,
                }
                
                # Include id if present (initial chunk)
                if "id" in tc_raw:
                    tool_call_entry["id"] = tc_raw["id"]
                
                # Include type and function if present
                if "type" in tc_raw and tc_raw["type"] == "function":
                    tool_call_entry["type"] = "function"
                
                # Handle function field
                if "function" in tc_raw:
                    func_raw = tc_raw["function"]
                    func_entry: dict[str, str] = {}
                    
                    if "name" in func_raw:
                        func_entry["name"] = func_raw["name"]
                    
                    if "arguments" in func_raw:
                        func_entry["arguments"] = func_raw["arguments"]
                    
                    if func_entry:
                        tool_call_entry["function"] = func_entry
                
                tool_calls_delta.append(tool_call_entry)
        
        # Build delta
        delta = ChatCompletionChunkDelta(
            role=None,
            content=content,
            tool_calls=tool_calls_delta,
        )
        
        # Build choice
        choice = self._create_choice(
            delta=delta,
            finish_reason=finish_reason,
        )
        
        chunk.choices = [choice]
        chunk.usage = usage
        
        return chunk
