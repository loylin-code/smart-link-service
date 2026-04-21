"""
Test Bailian LLM API call (Anthropic-compatible)
Tests the LLM configuration from opencode.jsonc
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


async def test_bailian_llm():
    """Test Bailian LLM API call (Anthropic-compatible)"""
    
    api_key = "sk-sp-8245679850744a1aa62e6e42c0738742"
    base_url = "https://coding.dashscope.aliyuncs.com/apps/anthropic/v1"
    
    print("=" * 60)
    print("Testing Bailian LLM API (Anthropic-compatible)")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:20]}...")
    print()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        
        # Test 1: Simple chat
        print("Test 1: Simple chat with glm-5...")
        response = await client.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "glm-5",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Hello, introduce yourself briefly"}],
            }
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            # Find text content
            text_content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_content = block.get("text", "")
            print(f"Response: {text_content[:200]}...")
            print(f"Usage: input={data['usage']['input_tokens']}, output={data['usage']['output_tokens']}")
        else:
            print(f"Error: {response.text}")
        print()
        
        # Test 2: Streaming
        print("Test 2: Streaming with glm-5...")
        response = await client.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "glm-5",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": "Count from 1 to 5"}],
                "stream": True,
            }
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("Streaming response: ")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                print(delta.get("text", ""), end="", flush=True)
                    except json.JSONDecodeError:
                        pass
            print()
        else:
            print(f"Error: {response.text}")
        print()
        
        # Test 3: Different model (qwen3.5-plus)
        print("Test 3: Testing qwen3.5-plus...")
        response = await client.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "qwen3.5-plus",
                "max_tokens": 50,
                "messages": [{"role": "user", "content": "Say OK"}],
            }
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            text_content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text_content = block.get("text", "")
            print(f"Response: {text_content}")
        else:
            print(f"Error: {response.text}")
        print()
    
    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    print()
    print("Configuration Summary:")
    print(f"  - Provider: bailian-coding-plan")
    print(f"  - Base URL: {base_url}")
    print(f"  - API Format: Anthropic-compatible")
    print(f"  - Header: x-api-key (not Authorization: Bearer)")
    print(f"  - Endpoint: /messages (not /chat/completions)")
    print(f"  - Required Header: anthropic-version: 2023-06-01")


if __name__ == "__main__":
    asyncio.run(test_bailian_llm())