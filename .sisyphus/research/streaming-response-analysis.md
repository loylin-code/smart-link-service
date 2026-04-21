# Chat Completions 流式响应完整分析方案

**生成日期**: 2026-04-21  
**研究目标**: 解决 SmartLink 后端 Chat Completions API (`/api/v1/chat/completions`) 流式响应问题  
**错误信息**: `'ReActAgent' object has no attribute 'stream_reply'`

---

## 一、问题背景

### 1.1 原始错误

```
data: {"error": "'ReActAgent' object has no attribute 'stream_reply'"}
```

### 1.2 修复历史

| 问题 | 修复 | Commit |
|------|------|--------|
| Chat completions 路径 404 | 注册 chat_completions.router | ed5b6da |
| MCP servers 启动错误 | 禁用模板服务器 | 759edcf |
| execute_stream_openai 缺失 | 添加方法到 AgentOrchestrator | 0b1ea04 |
| ReActAgent model_config 错误 | 重写 AgentFactory 创建正确模型 | d765736 |
| stream_reply 不存在 | 修改 execute_stream 用 LLMClient.chat_stream | 6f5441e |

### 1.3 核心问题

**AgentScope 的 `ReActAgent` 没有 `stream_reply` 方法！**

---

## 二、AgentScope 流式响应分析

### 2.1 核心发现：累积式流式（Accumulative Streaming）

AgentScope 使用 **累积式流式**，而非增量式：

```
# 增量式（OpenAI 标准）          # 累积式（AgentScope）
chunk 1: "H"                    chunk 1: "H"
chunk 2: "e"                    chunk 2: "He"
chunk 3: "l"                    chunk 3: "Hel"
chunk 4: "l"                    chunk 4: "Hell"
chunk 5: "o"                    chunk 5: "Hello"
```

**优势**: 前端不需要追踪 delta，直接渲染完整内容  
**劣势**: 需要转换为 OpenAI 增量格式才能兼容 OpenAI API

### 2.2 正确用法

**流式配置在模型构造时**：

```python
from agentscope.model import DashScopeChatModel
from agentscope.agent import ReActAgent

model = DashScopeChatModel(
    model_name="qwen-max",
    stream=True,  # 在构造时启用流式
)

agent = ReActAgent(
    name="Assistant",
    model=model,  # 模型带 stream=True
    toolkit=toolkit,
)

# ReActAgent 内部处理流式
response = await agent(msg)  # 不是 stream_reply()
```

**关键点**：
- `ReActAgent` 没有 `stream_reply` 方法
- 流式在 `ChatModel` 构造时配置
- `agent(msg)` 返回的 response 已处理流式

### 2.3 ReActAgent 内部流式处理流程

```
agent(msg)
    ↓
ReActAgent.reply()
    ↓
model(formatted_messages)  # 返回 AsyncGenerator
    ↓
[内部迭代 chunks]
    ↓
累积 chunks → ChatResponse
    ↓
返回最终 response
```

**问题**: 如果要在 **外部获取流式 chunks**，需要绕过 ReActAgent，直接使用 ChatModel。

### 2.4 ChatResponse 结构

```python
@dataclass
class ChatResponse:
    content: list[TextBlock | ThinkingBlock | ToolUseBlock]
    role: str  # "assistant"
    metadata: dict
    usage: ChatUsage  # 仅在最终 chunk 中
```

---

## 三、LiteLLM 流式响应分析

### 3.1 基本用法

```python
from litellm import acompletion

async def stream():
    response = await acompletion(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True,
        stream_options={"include_usage": True}  # 包含使用统计
    )
    
    async for chunk in response:
        delta = chunk.choices[0].delta
        content = delta.content or ""
        finish_reason = chunk.choices[0].finish_reason
        
        if content:
            yield content
        if finish_reason:
            break
```

### 3.2 Chunk 格式

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion.chunk",
  "created": 1234567890,
  "model": "gpt-4o",
  "choices": [{
    "index": 0,
    "delta": {
      "role": "assistant",  // 第一个 chunk
      "content": "Hello"    // 内容 chunks
    },
    "finish_reason": null   // null 或 "stop" 或 "length"
  }],
  "usage": {...}  // 最终 chunk (如果 stream_options.include_usage=True)
}
```

### 3.3 错误处理

**无限循环检测**:
```python
import litellm
litellm.REPEATED_STREAMING_CHUNK_LIMIT = 100  # 默认值
```

**超时和重试**:
```python
try:
    response = await acompletion(model=..., stream=True, timeout=30.0)
    async for chunk in response:
        yield chunk
except litellm.Timeout:
    # 重试逻辑
except litellm.InternalServerError as e:
    if "repeating" in str(e):
        # 模型无限循环
```

---

## 四、FastAPI SSE 最佳实践

### 4.1 标准 SSE 格式

```
data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"H"}}]}

data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"e"}}]}

data: [DONE]

```

**规则**:
- 每个 chunk: `data: {json}\n\n`
- 结束标记: `data: [DONE]\n\n`

### 4.2 StreamingResponse 配置

```python
from fastapi.responses import StreamingResponse

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    async def generate():
        # 检查断开连接（关键！）
        if await request.is_disconnected():
            break
        yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
```

### 4.3 必须实现的特性

| 特性 | 说明 |
|------|------|
| `request.is_disconnected()` | **必须检查**，否则资源泄漏 |
| 心跳机制 | 每 15 秒发送 `: heartbeat\n\n` |
| 错误处理 | 流中错误 → SSE 错误事件 |
| Nginx 配置 | `proxy_buffering off` |

### 4.4 心跳机制

```python
async def event_generator(request: Request):
    last_event_time = time.time()
    heartbeat_interval = 15
    
    while True:
        if await request.is_disconnected():
            break
        
        if time.time() - last_event_time > heartbeat_interval:
            yield ": heartbeat\n\n"
            last_event_time = time.time()
        
        # 正常事件
        yield f"data: {json.dumps(data)}\n\n"
```

---

## 五、本地代码分析

### 5.1 流式架构（已实现）

```
POST /api/v1/chat/completions
    ↓
chat_completions.py:stream_generator()
    ↓
AgentOrchestrator.execute_stream_openai()
    ↓
AgentOrchestrator.execute_stream()
    ↓
LLMClient.chat_stream_openai()  # 或 chat_stream()
    ↓
litellm.acompletion(stream=True)
    ↓
[AsyncIterator yields chunks]
    ↓
ChunkBuilder → ChatCompletionChunk
    ↓
.to_sse_line() → "data: {...}\n\n"
    ↓
StreamingResponse → Client
```

### 5.2 关键文件

| 文件 | 作用 |
|------|------|
| `agent/llm/client.py` | LLMClient，chat_stream/chat_stream_openai 方法 |
| `agent/core/orchestrator.py` | execute_stream, execute_stream_openai |
| `agent/core/chunk_builder.py` | ChunkBuilder 转换 LiteLLM → OpenAI 格式 |
| `schemas/openai_compat.py` | ChatCompletionChunk + to_sse_line() |
| `gateway/api/v1/chat_completions.py` | SSE 端点 |

### 5.3 ChunkBuilder 能力

| 方法 | 用途 |
|------|------|
| `build_role_chunk()` | 第一个 chunk: `role: "assistant"` |
| `build_content_chunk(content)` | 文本增量 chunks |
| `build_tool_call_chunk()` | 工具调用 chunks |
| `build_final_chunk(finish_reason, usage)` | 最终 chunk |
| `from_litellm_chunk()` | LiteLLM dict → ChatCompletionChunk |

### 5.4 当前状态

**流式基础设施已完整**。需要验证：
1. 后端是否已重启（旧代码可能仍在运行）
2. orchestrator.py execute_stream 是否正确使用 LLMClient

---

## 六、推荐解决方案

### 6.1 方案 A：重启后端验证（最简单）

```bash
cd E:\programe\ai\smart-link-service
uvicorn gateway.main:app --reload --port 8000
```

测试：
```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{"model": "agent:test-agent", "messages": [{"role": "user", "content": "Hello"}], "stream": true}'
```

### 6.2 方案 B：正确实现 execute_stream（绕过 ReActAgent）

**核心问题**：ReActAgent 没有 stream_reply 方法，且内部处理流式。

**解决思路**：直接使用 LLMClient.chat_stream，绕过 ReActAgent。

```python
# agent/core/orchestrator.py

async def execute_stream(self, agent_id, input_data, conversation_id=None):
    """流式执行 - 直接使用 LLMClient"""
    
    # 1. 加载 agent 配置
    role_config = await self._load_agent_config(agent_id)
    
    # 2. 构建 system prompt
    identity = role_config.get("identity", {})
    sys_prompt = f"# {identity.get('name', 'Assistant')}\n\n{identity.get('persona', '')}"
    
    # 3. 获取模型配置
    capabilities = role_config.get("capabilities", {})
    llm_config = capabilities.get("llm", {})
    model = llm_config.get("model", "gpt-4o-mini")
    
    # 4. 直接使用 LLMClient（关键！）
    from agent.llm.client import LLMClient
    llm_client = LLMClient({"model": model})
    
    # 5. 构建消息
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": input_data.get("message", "")}
    ]
    
    # 6. 流式生成
    async for chunk in llm_client.chat_stream(messages):
        yield {
            "type": "chunk",
            "content": chunk.get("content", ""),
            "done": False
        }
        if chunk.get("finish_reason"):
            yield {"type": "complete", "content": "", "done": True}
            break
```

### 6.3 方案 C：完整 OpenAI 兼容实现（生产级）

```python
# agent/core/orchestrator.py

async def execute_stream_openai(
    self,
    agent_id: str,
    execution_id: str,
    input_data: dict,
    include_usage: bool = False
) -> AsyncIterator[ChatCompletionChunk]:
    """OpenAI 兼容流式响应"""
    
    chunk_id = f"chatcmpl-{uuid.uuid4()}"
    created = int(time.time())
    
    # 加载配置
    role_config = await self._load_agent_config(agent_id)
    model = role_config.get("capabilities", {}).get("llm", {}).get("model", "gpt-4o-mini")
    
    # 使用 ChunkBuilder
    from agent.core.chunk_builder import ChunkBuilder
    builder = ChunkBuilder(chunk_id, created, f"agent:{agent_id}")
    
    # 第一个 chunk: role
    yield builder.build_role_chunk()
    
    # 流式生成
    from agent.llm.client import LLMClient
    llm_client = LLMClient({"model": model})
    
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": input_data.get("message", "")}
    ]
    
    accumulated_content = ""
    async for chunk in llm_client.chat_stream_openai(messages):
        delta_content = chunk.get("content", "")
        
        # 计算增量（从累积式中提取）
        incremental = delta_content[len(accumulated_content):]
        accumulated_content = delta_content
        
        if incremental:
            yield builder.build_content_chunk(incremental)
        
        if chunk.get("finish_reason"):
            usage = chunk.get("usage") if include_usage else None
            yield builder.build_final_chunk(
                chunk.get("finish_reason"),
                usage
            )
            break
```

### 6.4 SSE 端点完整实现

```python
# gateway/api/v1/chat_completions.py

async def stream_generator(
    orchestrator: AgentOrchestrator,
    agent_id: str,
    execution_id: str,
    data: ChatCompletionRequest,
    request: Request
) -> AsyncIterator[str]:
    """生产级 SSE 生成器"""
    
    try:
        async for chunk in orchestrator.execute_stream_openai(
            agent_id,
            execution_id,
            {"message": data.messages[-1].content},
            include_usage=data.stream_options.include_usage if data.stream_options else False
        ):
            # 检查断开连接
            if await request.is_disconnected():
                logger.info(f"Client disconnected: {execution_id}")
                break
            
            yield chunk.to_sse_line()
        
        if not await request.is_disconnected():
            yield "data: [DONE]\n\n"
    
    except asyncio.CancelledError:
        logger.info(f"Stream cancelled: {execution_id}")
    except AgentError as e:
        yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'agent_error'}})}\n\n"
    except LLMError as e:
        yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'llm_error'}})}\n\n"
    except Exception as e:
        logger.exception(f"Unexpected error: {execution_id}")
        yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'internal_error'}})}\n\n"


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    data: ChatCompletionRequest,
    authorization: str = Header(None)
):
    """OpenAI 兼容 Chat Completions API"""
    
    # 验证
    if not data.stream:
        return await handle_non_stream(data)
    
    # 解析 agent_id
    agent_id = data.model.replace("agent:", "")
    
    # 创建 execution
    execution_id = str(uuid.uuid4())
    
    orchestrator = AgentOrchestrator()
    
    return StreamingResponse(
        stream_generator(orchestrator, agent_id, execution_id, data, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        }
    )
```

---

## 七、关键决策点

### 7.1 是否需要 ReActAgent？

| 场景 | 建议 |
|------|------|
| 仅聊天（无工具） | 不需要 ReActAgent，直接 LLMClient |
| 需要工具调用 | 需要 ReActAgent，但流式需要特殊处理 |
| OpenAI 兼容 API | 建议 LLMClient 直接流式 |

### 7.2 流式响应转换

**AgentScope 累积式 → OpenAI 增量式**：

```python
accumulated = ""
async for chunk in agent_model(messages):
    # AgentScope chunk.content 是累积的
    full_content = extract_text(chunk.content)
    
    # 计算增量
    delta = full_content[len(accumulated):]
    accumulated = full_content
    
    # 转换为 OpenAI chunk
    yield {"delta": {"content": delta}}
```

---

## 八、参考资料

### 8.1 AgentScope

| 主题 | URL |
|------|-----|
| Models Guide | https://docs.agentscope.io/building-blocks/models |
| Streaming Tutorial | https://doc.agentscope.io/tutorial/task_model.html#streaming |
| ReActAgent Quickstart | https://doc.agentscope.io/tutorial/quickstart_agent.html |
| GitHub Examples | https://github.com/agentscope-ai/agentscope/tree/main/examples |

### 8.2 LiteLLM

| 主题 | URL |
|------|-----|
| Streaming + Async | https://docs.litellm.ai/docs/completion/stream |
| Production Best Practices | https://docs.litellm.ai/docs/proxy/prod |
| Shared Session | https://docs.litellm.ai/docs/completion/shared_session |
| GitHub | https://github.com/BerriAI/litellm |

### 8.3 FastAPI SSE

| 主题 | URL |
|------|-----|
| Server-Sent Events | https://fastapi.tiangolo.com/tutorial/server-sent-events/ |
| OpenAI Streaming Format | https://developers.openai.com/api/reference/chat/streaming |
| SSE Best Practices | https://medium.com/@ThinkingLoop/10-fastapi-patterns-for-streamed-responses |

---

## 九、总结

### 问题根因
- AgentScope `ReActAgent` 没有 `stream_reply` 方法
- 流式配置在 ChatModel 构造时，而非调用时

### 解决方案
- **直接使用 LLMClient.chat_stream**，绕过 ReActAgent
- **转换为增量式**，适配 OpenAI 格式
- **实现 SSE 最佳实践**：断开检测、心跳、错误处理

### 下一步
1. 重启后端验证修改
2. 测试流式响应
3. 如有问题，按方案 B/C 修正代码