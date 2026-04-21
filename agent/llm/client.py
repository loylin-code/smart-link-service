"""
LLM client with multi-provider support using LiteLLM
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
import litellm
from litellm import acompletion

from core.config import settings
from core.exceptions import LLMError
from agent.cache import llm_cache
from agent.llm.retry import is_retryable_error, get_wait_time

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM client supporting multiple providers via LiteLLM
    Supports: OpenAI, Anthropic, Azure, Bailian, local models, etc.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize LLM client
        
        Args:
            config: LLM configuration with provider, model, api_key, etc.
        """
        self.config = config or {}
        
        # Set default provider and model
        self.provider = self.config.get("provider", settings.DEFAULT_LLM_PROVIDER)
        self.model = self.config.get("model", settings.DEFAULT_LLM_MODEL)
        
        # Retry configuration
        self.max_retries = settings.LLM_MAX_RETRIES
        
        # Provider-specific configuration
        self.api_key = self.config.get("api_key")
        self.api_base = self.config.get("api_base")
        
        # Configure LiteLLM
        self._configure_litellm()
    
    def _configure_litellm(self):
        """Configure LiteLLM with API keys"""
        # Set API keys from settings
        if settings.OPENAI_API_KEY:
            litellm.api_key = settings.OPENAI_API_KEY
        
        if settings.ANTHROPIC_API_KEY:
            # LiteLLM will use this for Anthropic models
            pass
        
        # Enable caching (optional)
        litellm.cache = None  # Can configure Redis cache here
        
        # Set default parameters
        litellm.set_verbose = settings.DEBUG
    
    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Get provider-specific configuration for LiteLLM
        
        Returns:
            Dict with api_key, api_base for the provider
        """
        extra_params = {}
        
        # Handle OpenAI or any OpenAI-compatible provider
        if self.provider == "openai":
            # Use OPENAI_API_KEY and OPENAI_BASE_URL from settings
            if settings.OPENAI_API_KEY:
                extra_params["api_key"] = settings.OPENAI_API_KEY
            if settings.OPENAI_BASE_URL:
                extra_params["api_base"] = settings.OPENAI_BASE_URL
            # Allow override via config
            if self.api_key:
                extra_params["api_key"] = self.api_key
            if self.api_base:
                extra_params["api_base"] = self.api_base
        
        return extra_params
    
    def _get_model_string(self) -> str:
        """
        Get model string for LiteLLM
        
        LiteLLM format: "provider/model"
        Examples: 
            - "openai/gpt-4"
            - "anthropic/claude-3-5-sonnet-20241022"
            - "ollama/llama2"
        """
        if "/" in self.model:
            # Already in correct format
            return self.model
        
        # Prepend provider
        return f"{self.provider}/{self.model}"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = "auto",
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request with caching and retry.
        
        Args:
            messages: List of message dicts with role and content
            tools: List of tool definitions (OpenAI format)
            tool_choice: Tool choice strategy ("auto", "none", or specific)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Response dict with content, tool_calls, usage
        """
        # Initialize cache if needed
        if llm_cache.enabled and not llm_cache._initialized:
            await llm_cache.initialize()
        
        # Extract prompts for cache key
        system_prompt = next(
            (m.get('content', '') for m in messages if m.get('role') == 'system'),
            ""
        )
        user_message = next(
            (m.get('content', '') for m in messages if m.get('role') == 'user'),
            ""
        )
        
        # Check cache (only if no tools - tool calls vary)
        if llm_cache.enabled and not tools:
            cached = await llm_cache.get(
                system_prompt=system_prompt,
                user_message=user_message,
                model=self.model
            )
            if cached:
                return cached  # Cache hit
        
        # Retry loop
        for attempt in range(self.max_retries + 1):
            try:
                # Build request
                request_params = {
                    "model": self._get_model_string(),
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                
                # Add provider-specific config (api_key, api_base)
                request_params.update(self._get_provider_config())
                
                # Add tools if provided
                if tools:
                    request_params["tools"] = tools
                    request_params["tool_choice"] = tool_choice
                
                # Add extra params
                request_params.update(kwargs)
                
                # Call LLM
                response = await acompletion(**request_params)
                
                # Extract result
                message = response.choices[0].message
                
                result = {
                    "content": message.content or "",
                    "role": message.role,
                }
                
                # Extract tool calls if present
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                
                # Add usage info
                if hasattr(response, 'usage'):
                    result["usage"] = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                
                # Store in cache (only if no tools)
                if llm_cache.enabled and not tools:
                    await llm_cache.set(
                        system_prompt=system_prompt,
                        user_message=user_message,
                        model=self.model,
                        provider=self.provider,
                        response=result,
                        tokens_used=result.get("usage", {}).get("total_tokens", 0)
                    )
                
                return result
                
            except Exception as e:
                # Check if retryable
                if not is_retryable_error(e):
                    # Non-retryable error - raise immediately
                    raise LLMError(
                        f"LLM request failed (non-retryable): {str(e)}",
                        provider=self.provider
                    )
                
                # Check if max retries exhausted
                if attempt >= self.max_retries:
                    raise LLMError(
                        f"LLM request failed after {self.max_retries} retries: {str(e)}",
                        provider=self.provider
                    )
                
                # Calculate wait time
                wait_time = get_wait_time(e, attempt)
                
                # Log retry attempt
                logger.warning(
                    f"LLM call failed, retrying",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "wait_seconds": wait_time,
                        "provider": self.provider,
                        "model": self.model,
                    }
                )
                
                # Wait before retry
                await asyncio.sleep(wait_time)
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream chat completion
        
        Args:
            messages: List of message dicts
            tools: List of tool definitions
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Yields:
            Stream chunks with content delta
        """
        try:
            # Build request
            request_params = {
                "model": self._get_model_string(),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            
            # Add provider-specific config (api_key, api_base)
            request_params.update(self._get_provider_config())
            
            if tools:
                request_params["tools"] = tools
            
            request_params.update(kwargs)
            
            # Stream response
            async for chunk in await acompletion(**request_params):
                delta = chunk.choices[0].delta
                
                yield {
                    "content": delta.content or "",
                    "finish_reason": chunk.choices[0].finish_reason
                }
                
        except Exception as e:
            raise LLMError(
                f"LLM streaming failed: {str(e)}",
                provider=self.provider
            )
    
    async def chat_stream_openai(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = "auto",
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = 4096,
        stream_options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream chat completion in OpenAI format
        
        Args:
            messages: List of message dicts with role and content
            tools: List of tool definitions (OpenAI format)
            tool_choice: Tool choice strategy ("auto", "none", "required", or specific)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream_options: Additional streaming options (e.g., {"include_usage": True})
            **kwargs: Additional parameters
            
        Yields:
            Stream chunks in OpenAI format:
            {
                "content": str,           # Text delta
                "finish_reason": str,      # "stop", "tool_calls", or None
                "tool_calls": [...],       # Tool calls delta (optional)
                "usage": {...}             # Usage info in last chunk (optional)
            }
        """
        try:
            # Build request
            request_params = {
                "model": self._get_model_string(),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            
            # Add provider-specific config (api_key, api_base)
            request_params.update(self._get_provider_config())
            
            # Add tools if provided
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice
            
            # Add stream_options if provided
            if stream_options:
                request_params["stream_options"] = stream_options
            
            # Add extra params
            request_params.update(kwargs)
            
            # Stream response
            async for chunk in await acompletion(**request_params):
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason
                
                # Build response chunk
                response_chunk = {
                    "content": delta.content or "",
                    "finish_reason": finish_reason,
                }
                
                # Convert tool_calls if present
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    tool_calls_list = []
                    for tc in delta.tool_calls:
                        tool_call_dict = {
                            "index": tc.index if hasattr(tc, 'index') else 0,
                            "id": tc.id if hasattr(tc, 'id') else "",
                            "type": tc.type if hasattr(tc, 'type') else "function",
                        }
                        
                        # Handle function field
                        if hasattr(tc, 'function') and tc.function:
                            tool_call_dict["function"] = {
                                "name": tc.function.name if hasattr(tc.function, 'name') else "",
                                "arguments": tc.function.arguments if hasattr(tc.function, 'arguments') else ""
                            }
                        
                        tool_calls_list.append(tool_call_dict)
                    
                    response_chunk["tool_calls"] = tool_calls_list
                
                # Add usage if present (typically in last chunk)
                if hasattr(chunk, 'usage') and chunk.usage:
                    response_chunk["usage"] = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens
                    }
                
                yield response_chunk
                
        except Exception as e:
            raise LLMError(
                f"LLM streaming (OpenAI format) failed: {str(e)}",
                provider=self.provider
            )
    
    async def embed(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for texts
        
        Args:
            texts: List of texts to embed
            model: Embedding model (optional)
            
        Returns:
            List of embedding vectors
        """
        try:
            from litellm import aembedding
            
            model_str = model or "text-embedding-ada-002"
            if "/" not in model_str:
                model_str = f"{self.provider}/{model_str}"
            
            response = await aembedding(
                model=model_str,
                input=texts
            )
            
            return [item["embedding"] for item in response.data]
            
        except Exception as e:
            raise LLMError(
                f"Embedding generation failed: {str(e)}",
                provider=self.provider
            )