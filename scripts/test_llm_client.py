"""
Test LLMClient with Bailian (阿里百炼)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.llm.client import LLMClient


async def test_llm_client():
    """Test LLMClient with Bailian"""
    
    print("=" * 60)
    print("Testing LLMClient with Bailian (Anthropic-compatible)")
    print("=" * 60)
    
    client = LLMClient()
    print(f"Provider: {client.provider}")
    print(f"Model: {client.model}")
    print(f"Model string: {client._get_model_string()}")
    print()
    
    # Test 1: Simple chat
    print("Test 1: Simple chat...")
    try:
        result = await client.chat(
            messages=[{"role": "user", "content": "Hello, say OK"}],
            max_tokens=20,
        )
        print(f"Success!")
        print(f"Response: {result.get('content', '')[:100]}")
        print()
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {str(e)[:200]}")
        print()
    
    # Test 2: Streaming
    print("Test 2: Streaming...")
    try:
        print("Response: ", end="", flush=True)
        async for chunk in client.chat_stream(
            messages=[{"role": "user", "content": "Count 1 to 3"}],
            max_tokens=20,
        ):
            if chunk.get("content"):
                print(chunk["content"], end="", flush=True)
        print()
        print("Streaming completed!")
        print()
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {str(e)[:200]}")
        print()
    
    # Test 3: Different model
    print("Test 3: Testing qwen3.5-plus...")
    try:
        client2 = LLMClient({"model": "qwen3.5-plus"})
        result = await client2.chat(
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
        )
        print(f"Success!")
        print(f"Response: {result.get('content', '')}")
        print()
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {str(e)[:200]}")
        print()
    
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_llm_client())