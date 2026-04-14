"""
LLM client with multi-provider support using LiteLLM
"""
from typing import Dict, Any, List, Optional, AsyncIterator
import litellm
from litellm import acompletion

from core.config import settings
from core.exceptions import LLMError
from agent.cache import llm_cache


class LLMClient:
    """
    LLM client supporting multiple providers via LiteLLM
    Supports: OpenAI, Anthropic, Azure, local models, etc.
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
        Send chat completion request with caching.
        
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
        
        try:
            # Build request
            request_params = {
                "model": self._get_model_string(),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
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
            raise LLMError(
                f"LLM request failed: {str(e)}",
                provider=self.provider
            )
    
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