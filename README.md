# SmartLink Agent Management Platform - Backend Service

<div align="center">

**基于LLM的Agent管理平台后端服务**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-brightgreen.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

</div>

---

## 📖 项目简介

SmartLink是一个**生产就绪**的LLM Agent管理平台后端服务，采用三层架构设计（Gateway → Service → Agent），提供完整的Agent编排、资源管理、实时通信能力。

### 核心特性

- 🚀 **高性能架构** - FastAPI异步框架，支持高并发
- 🤖 **多LLM支持** - 通过LiteLLM支持OpenAI、Claude、Ollama等
- 🔧 **插件化Skill系统** - 可扩展的技能插件，自动发现注册
- 📡 **WebSocket实时通信** - 支持流式响应和实时进度
- 🔐 **API Key认证** - 简单安全的认证机制
- 💾 **可靠存储** - PostgreSQL持久化 + Redis缓存
- 🐳 **容器化部署** - Docker Compose一键启动

## 🏗️ 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        SmartLink Platform                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │   Frontend   │◄───────►│   Gateway    │                     │
│  │   (Vue 3)    │  WS/HTTP│   Service    │                     │
│  └──────────────┘         └──────┬───────┘                     │
│                                  │                               │
│                                  ▼                               │
│                         ┌──────────────┐                        │
│                         │Message Router│                        │
│                         │   (Redis)    │                        │
│                         └──────┬───────┘                        │
│                                  │                               │
│                    ┌─────────────┼─────────────┐               │
│                    ▼             ▼             ▼               │
│              ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│              │ Agent 1  │ │ Agent 2  │ │ Agent N  │           │
│              │          │ │          │ │          │           │
│              │ • Skills │ │ • Skills │ │ • Skills │           │
│              │ • MCP    │ │ • MCP    │ │ • MCP    │           │
│              │ • Tools  │ │ • Tools  │ │ • Tools  │           │
│              │ • LLM    │ │ • LLM    │ │ • LLM    │           │
│              └──────────┘ └──────────┘ └──────────┘           │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Shared Infrastructure                       │    │
│  │  • PostgreSQL (持久化)  • Redis (缓存/队列)              │    │
│  │  • MinIO (对象存储)     • Prometheus (监控)              │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                       │
│  • WebSocket连接管理                                         │
│  • HTTP REST API                                             │
│  • 认证/授权                                                 │
│  • 请求路由                                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Service Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   App       │  │  Resource   │  │    AI       │         │
│  │  Service    │  │  Service    │  │  Service    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Agent Runtime Layer                       │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Agent Orchestrator                                    │ │
│  │  • Agent生命周期管理                                    │ │
│  │  • Skill/Tool注册与调度                                 │ │
│  │  • MCP协议处理                                         │ │
│  │  • LLM调用编排                                         │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Skill Engine │  │  MCP Client  │  │  LLM Client  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
smart-link-service/
├── gateway/                    # 网关层
│   ├── api/                   # REST API路由
│   │   └── v1/
│   │       ├── applications.py    # 应用管理API
│   │       ├── resources.py       # 资源管理API
│   │       └── websocket.py       # WebSocket端点
│   ├── websocket/             # WebSocket处理
│   │   ├── manager.py             # 连接管理器
│   │   └── handlers.py            # 消息处理器
│   └── middleware/            # 中间件
│       ├── auth.py                # API Key认证
│       └── logging.py             # 请求日志
│
├── services/                  # 业务服务层
│   ├── application_service.py     # 应用服务
│   ├── resource_service.py        # 资源服务
│   └── conversation_service.py    # 对话服务
│
├── agent/                     # Agent运行时
│   ├── core/                  # 核心引擎
│   │   ├── orchestrator.py        # 编排器
│   │   └── context.py             # 上下文管理
│   ├── llm/                   # LLM集成
│   │   └── client.py              # LLM客户端(LiteLLM)
│   └── skills/                # Skills插件
│       ├── base.py                # Skill基类
│       ├── registry.py            # Skill注册表
│       └── builtin/               # 内置Skills
│           └── search.py
│
├── models/                    # 数据模型
│   └── application.py             # Application, Conversation等
│
├── schemas/                   # Pydantic Schemas
│   └── common.py                  # API请求/响应Schema
│
├── core/                      # 核心配置
│   ├── config.py                  # 配置管理
│   ├── security.py                # 安全工具
│   └── exceptions.py              # 异常定义
│
├── db/                        # 数据库
│   └── session.py                 # 数据库会话管理
│
├── docker/                    # Docker配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── start-dev.bat             # Windows启动脚本
│   └── start-dev.sh              # Linux/Mac启动脚本
│
├── scripts/                   # 工具脚本
│   └── init_db.py                 # 数据库初始化
│
├── pyproject.toml             # 项目配置
├── requirements.txt           # Python依赖
├── .env.example               # 环境变量示例
└── README.md
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL 15+ (或使用Docker)
- Redis 7+ (或使用Docker)

### 安装步骤

#### 1. 克隆项目

```bash
git clone <repository-url>
cd smart-link-service
```

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的参数
```

关键配置项：
```env
# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/smartlink

# Redis
REDIS_URL=redis://localhost:6379/0

# 安全
MASTER_API_KEY=sk-smartlink-master-key-change-in-production
SECRET_KEY=your-secret-key-min-32-chars

# LLM（至少配置一个）
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

#### 3. 使用Docker启动（推荐）

**Windows:**
```bash
cd docker
start-dev.bat
```

**Linux/Mac:**
```bash
cd docker
chmod +x start-dev.sh
./start-dev.sh
```

#### 4. 或手动启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动依赖服务（需要先安装PostgreSQL和Redis）
# 初始化数据库
python scripts/init_db.py

# 启动服务
uvicorn gateway.main:app --reload
```

### 访问服务

启动成功后，访问以下地址：

- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health

## 📚 API使用示例

### 1. 创建应用

```bash
curl -X POST http://localhost:8000/api/v1/applications \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-smartlink-master-key-change-in-production" \
  -d '{
    "name": "智能客服助手",
    "description": "基于LLM的智能客服系统",
    "type": "workflow"
  }'
```

### 2. 获取应用列表

```bash
curl -X GET "http://localhost:8000/api/v1/applications?page=1&page_size=20" \
  -H "X-API-Key: sk-smartlink-master-key-change-in-production"
```

### 3. WebSocket聊天

```javascript
const ws = new WebSocket(
  'ws://localhost:8000/ws/chat/client-123?' +
  'app_id=app_xxx&' +
  'api_key=sk-smartlink-master-key-change-in-production'
);

ws.onopen = () => {
  // 发送消息
  ws.send(JSON.stringify({
    type: 'chat',
    data: {
      message: '你好，请介绍一下自己',
      app_id: 'app_xxx'
    }
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
  
  if (data.type === 'response') {
    // 处理响应
    console.log('AI回复:', data.data.message.content);
  }
};
```

## 🔧 核心概念

### Application（应用）

应用是Agent的容器，包含工作流配置、Skills、Tools等。

**应用类型：**
- `workflow` - 工作流应用
- `chart` - 图表应用
- `form` - 表单应用
- `dashboard` - 仪表盘应用
- `custom` - 自定义应用

**应用状态：**
- `draft` - 草稿
- `designing` - 设计中
- `published` - 已发布
- `archived` - 已归档

### Skill（技能）

可复用的能力模块，如网络搜索、数据分析等。

**内置Skills：**
- `web_search` - 网络搜索
- `data_analysis` - 数据分析

### MCP (Model Context Protocol)

Anthropic提出的模型上下文协议，用于标准化工具调用。

### Workflow（工作流）

节点和边组成的有向图，定义Agent的执行流程。

## 🛠️ 开发指南

### 添加新的Skill

1. 在 `agent/skills/builtin/` 目录下创建新文件：

```python
# agent/skills/builtin/my_skill.py
from agent.skills.base import BaseSkill
from agent.core.context import AgentContext

class MySkill(BaseSkill):
    name = "my_skill"
    description = "我的自定义技能"
    version = "1.0.0"
    
    async def execute(self, context: AgentContext, params: dict):
        # 实现技能逻辑
        result = {"status": "success", "data": "processed"}
        return result
    
    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "输入参数"
                }
            },
            "required": ["input"]
        }
```

2. 系统会自动发现并注册该Skill。

### 添加新的API端点

1. 在 `gateway/api/v1/` 目录下创建路由文件：

```python
# gateway/api/v1/my_router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db

router = APIRouter()

@router.get("/my-endpoint")
async def my_endpoint(db: AsyncSession = Depends(get_db)):
    return {"message": "success"}
```

2. 在 `gateway/api/v1/__init__.py` 中注册：

```python
from gateway.api.v1 import my_router

api_router.include_router(
    my_router.router,
    prefix="/my-router",
    tags=["my-router"]
)
```

## 📊 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| **Web框架** | FastAPI | 0.109+ |
| **ASGI服务器** | Uvicorn | 0.27+ |
| **数据库** | PostgreSQL | 15+ |
| **ORM** | SQLAlchemy | 2.0+ |
| **缓存** | Redis | 7+ |
| **LLM集成** | LiteLLM | 1.20+ |
| **Agent框架** | LangChain | 0.1+ |
| **验证** | Pydantic | 2.5+ |
| **容器化** | Docker | - |
| **编排** | Docker Compose | - |

## 🧪 测试

```bash
# 运行所有测试
pytest

# 带覆盖率报告
pytest --cov=. tests/

# 运行特定测试文件
pytest tests/test_api/test_applications.py
```

## 📦 部署

### Docker部署

```bash
# 构建镜像
docker build -f docker/Dockerfile -t smartlink-service:latest .

# 使用Docker Compose启动
docker-compose -f docker/docker-compose.yml up -d
```

### 生产环境建议

1. **安全配置**
   - 使用环境变量管理敏感信息
   - 启用HTTPS
   - 配置防火墙规则

2. **监控告警**
   - Prometheus + Grafana监控
   - ELK/Loki日志聚合
   - 配置告警规则

3. **高可用**
   - 使用Kubernetes编排
   - 配置负载均衡
   - 数据库主从复制

4. **性能优化**
   - 启用Redis缓存
   - 配置数据库连接池
   - 使用CDN加速静态资源

## 🔍 故障排查

### 数据库连接失败

```bash
# 检查PostgreSQL状态
docker-compose ps postgres

# 查看日志
docker-compose logs postgres

# 重启服务
docker-compose restart postgres
```

### Redis连接失败

```bash
# 检查Redis状态
docker-compose ps redis

# 测试连接
docker-compose exec redis redis-cli ping
```

### API Key无效

确保请求头中包含正确的 `X-API-Key`，且与 `.env` 中配置的 `MASTER_API_KEY` 一致。

## 🗺️ 开发路线

### ✅ 已完成

- [x] 核心架构搭建
- [x] Gateway层实现
- [x] Service层实现
- [x] Agent编排器基础
- [x] LLM集成(LiteLLM)
- [x] Skill插件系统
- [x] WebSocket支持
- [x] Docker部署

### 🚧 进行中

- [ ] MCP Server完整集成
- [ ] 工作流可视化编辑后端支持
- [ ] 更完善的错误处理
- [ ] 单元测试覆盖

### 📋 计划中

- [ ] 用户认证系统(JWT)
- [ ] 权限管理
- [ ] API限流
- [ ] 插件市场
- [ ] 监控仪表盘
- [ ] 国际化支持

## 🤝 贡献指南

我们欢迎所有形式的贡献！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

### 代码规范

- 使用Black格式化代码
- 遵循PEP 8规范
- 编写单元测试
- 更新相关文档

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👥 贡献者

感谢所有贡献者的付出！

## 📞 联系方式

- 项目主页: https://github.com/your-org/smart-link-service
- 问题反馈: https://github.com/your-org/smart-link-service/issues
- 邮箱: team@smartlink.com

## 🙏 致谢

本项目基于以下优秀的开源项目：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的Web框架
- [LiteLLM](https://github.com/BerriAI/litellm) - 统一的LLM接口
- [LangChain](https://www.langchain.com/) - LLM应用开发框架
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL工具包

---

<div align="center">

**Made with ❤️ by SmartLink Team**

</div>
