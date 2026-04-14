"""
Cache key generation for LLM responses
"""
import hashlib


def generate_cache_key(system_prompt: str, user_message: str, model: str) -> str:
    """
    Generate unique cache key for LLM request.
    
    Key composition: SHA-256 hash of (system_prompt | user_message | model)
    
    Args:
        system_prompt: Agent system prompt/identity
        user_message: User's input message
        model: LLM model name (e.g., "gpt-4o-mini")
    
    Returns:
        64-character SHA-256 hex digest
    """
    content = f"{system_prompt}|{user_message}|{model}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()