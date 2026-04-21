"""
Protocol Converter: OpenAI ChatCompletionChunk → Custom WebSocket Protocol

Converts OpenAI streaming format to custom WebSocket protocol format.

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

from typing import Any

from schemas.openai_compat import ChatCompletionChunk, UsageInfo


class ProtocolConverter:
    """
    OpenAI格式 → 自定义WebSocket协议转换器
    
    Converts OpenAI ChatCompletionChunk to custom WebSocket messages.
    Tracks accumulated tool_calls state for tools_ready message.
    """
    
    def __init__(self) -> None:
        """Initialize converter with empty tool_calls accumulator"""
        self._accumulated_tool_calls: dict[int, dict[str, str | None]] = {}
    
    def convert(
        self,
        chunk: ChatCompletionChunk,
        conversation_id: str,
        message_id: str
    ) -> list[dict[str, object]]:
        """
        转换单个OpenAI chunk为WebSocket消息列表
        
        Args:
            chunk: OpenAI ChatCompletionChunk
            conversation_id: Conversation ID
            message_id: Message ID
            
        Returns:
            List of WebSocket message dicts
        """
        messages: list[dict[str, object]] = []
        
        for choice in chunk.choices:
            delta = choice.delta
            finish_reason = choice.finish_reason
            
            # Handle role chunk (first chunk with role=assistant)
            if delta.role == "assistant":
                # Role chunk doesn't produce visible output
                continue
            
            # Handle content + finish_reason combination
            # When finish_reason=stop AND there's content, combine into one message
            if delta.content is not None and finish_reason == "stop":
                messages.append(
                    self._build_stream_message(
                        delta=delta.content,
                        done=True,
                        conversation_id=conversation_id,
                        message_id=message_id
                    )
                )
            else:
                # Handle content delta alone
                if delta.content is not None:
                    messages.append(
                        self._build_stream_message(
                            delta=delta.content,
                            done=False,
                            conversation_id=conversation_id,
                            message_id=message_id
                        )
                    )
                
                # Handle finish_reason alone
                if finish_reason == "stop":
                    # Stream message with done=true
                    messages.append(
                        self._build_stream_message(
                            delta=None,
                            done=True,
                            conversation_id=conversation_id,
                            message_id=message_id
                        )
                    )
                elif finish_reason == "tool_calls":
                    # Tools ready message with accumulated tool calls
                    messages.append(self._build_tools_ready_message())
                elif finish_reason in ("length", "content_filter"):
                    # Error message
                    messages.append(self._build_error_message(code=finish_reason))
            
            # Handle tool_calls delta
            if delta.tool_calls:
                tool_messages = self._process_tool_calls_delta(
                    tool_calls=delta.tool_calls
                )
                messages.extend(tool_messages)
        
        # Handle usage info (separate message)
        if chunk.usage:
            messages.append(self._build_usage_message(chunk.usage))
        
        return messages
    
    def _build_stream_message(
        self,
        delta: str | None,
        done: bool,
        conversation_id: str,
        message_id: str
    ) -> dict[str, object]:
        """
        构建stream消息
        
        Args:
            delta: Content delta (can be None)
            done: Whether stream is done
            conversation_id: Conversation ID
            message_id: Message ID
            
        Returns:
            WebSocket stream message dict
        """
        return {
            "type": "stream",
            "data": {
                "delta": delta,
                "done": done,
                "conversation_id": conversation_id,
                "message_id": message_id
            }
        }
    
    def _process_tool_calls_delta(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> list[dict[str, object]]:
        """
        处理tool_calls增量
        
        Args:
            tool_calls: List of tool call deltas from OpenAI
            
        Returns:
            List of tool_call messages
        """
        messages: list[dict[str, object]] = []
        
        for tool_call in tool_calls:
            index = tool_call.get("index", 0)
            
            # Initialize or update tool call
            if index not in self._accumulated_tool_calls:
                self._accumulated_tool_calls[index] = {
                    "tool_call_id": None,
                    "tool_name": None,
                    "arguments": ""
                }
            
            accumulated = self._accumulated_tool_calls[index]
            
            # Update tool_call_id if present
            if "id" in tool_call:
                accumulated["tool_call_id"] = tool_call["id"]
            
            # Update tool_name if present
            if "function" in tool_call and "name" in tool_call["function"]:
                accumulated["tool_name"] = tool_call["function"]["name"]
            
            # Update arguments if present
            if "function" in tool_call and "arguments" in tool_call["function"]:
                accumulated["arguments"] += tool_call["function"]["arguments"]
            
            # Build tool_call message
            tool_call_id = accumulated["tool_call_id"] or ""
            tool_name = accumulated["tool_name"] or ""
            
            message_data = {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "status": "calling"
            }
            
            # Include arguments_delta if this is an arguments update
            if "function" in tool_call and "arguments" in tool_call["function"]:
                message_data["arguments_delta"] = tool_call["function"]["arguments"]
            
            messages.append({
                "type": "tool_call",
                "data": message_data
            })
        
        return messages
    
    def _build_tools_ready_message(self) -> dict[str, object]:
        """
        构建tools_ready消息
        
        Uses accumulated tool_calls to build complete tool call list.
        
        Returns:
            WebSocket tools_ready message dict
        """
        tool_calls_list = []
        
        for index in sorted(self._accumulated_tool_calls.keys()):
            accumulated = self._accumulated_tool_calls[index]
            tool_calls_list.append({
                "tool_call_id": accumulated["tool_call_id"],
                "tool_name": accumulated["tool_name"],
                "arguments": accumulated["arguments"]
            })
        
        return {
            "type": "tools_ready",
            "data": {
                "tool_calls": tool_calls_list
            }
        }
    
    def _build_usage_message(self, usage: UsageInfo) -> dict[str, object]:
        """
        构建usage消息
        
        Args:
            usage: UsageInfo from OpenAI chunk
            
        Returns:
            WebSocket usage message dict
        """
        return {
            "type": "usage",
            "data": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }
        }
    
    def _build_error_message(
        self,
        code: str,
        message: str | None = None
    ) -> dict[str, object]:
        """
        构建error消息
        
        Args:
            code: Error code (e.g., "length", "content_filter")
            message: Optional error message
            
        Returns:
            WebSocket error message dict
        """
        return {
            "type": "error",
            "data": {
                "code": code,
                "message": message or f"Stream ended with {code}"
            }
        }
    
    def build_tool_result_message(
        self,
        tool_call_id: str,
        tool_name: str,
        result: str,
        success: bool
    ) -> dict[str, object]:
        """
        构建工具执行结果消息
        
        Args:
            tool_call_id: Tool call ID
            tool_name: Tool name
            result: Tool execution result
            success: Whether execution was successful
            
        Returns:
            WebSocket tool_result message dict
        """
        return {
            "type": "tool_result",
            "data": {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "result": result,
                "success": success
            }
        }
    
    def reset(self) -> None:
        """
        Reset accumulated tool_calls state
        
        Call this when starting a new conversation or after tools_ready.
        """
        self._accumulated_tool_calls.clear()


__all__ = ["ProtocolConverter"]