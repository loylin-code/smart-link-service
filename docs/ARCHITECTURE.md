# Enterprise Agent Application Management Platform
## Architecture Design Document

**Version:** 1.0  
**Date:** March 5, 2026  
**Status:** Design Specification  
**Scale Target:** 1,000 concurrent WebSocket connections, 10 tenants, 100 agent executions/minute

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Gateway Layer Design](#3-gateway-layer-design)
4. [Agent Distribution System](#4-agent-distribution-system)
5. [Multi-Tenant Architecture](#5-multi-tenant-architecture)
6. [Security Model](#6-security-model)
7. [Technology Stack](#7-technology-stack)
8. [Implementation Phases](#8-implementation-phases)

---

## 1. Executive Summary

### 1.1 Project Overview

SmartLink is an enterprise-grade Agent application management platform that enables organizations to design, orchestrate, and deploy AI-powered agent applications at scale. The platform follows an OpenClaw-inspired architecture with centralized gateway management and distributed agent execution.

### 1.2 Design Goals

| Goal | Description |
|------|-------------|
| **Enterprise-Ready** | Multi-tenant architecture with tenant isolation, OAuth2 authentication, and RBAC |
| **Scalable** | Support 1,000+ concurrent WebSocket connections with horizontal scaling |
| **Flexible** | Plugin-based skill system, MCP integration, customizable agent workflows |
| **Observable** | Built-in monitoring hooks, audit logging, metrics collection |
| **Production-Ready** | High availability, graceful degradation, automatic failover |

### 1.3 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tenant Isolation | Shared DB + tenant_id | Simple, suitable for 10 tenants, easy migration |
| Authentication | OAuth2 + JWT + API Keys | Enterprise SSO support, secure user auth, service-to-service |
| Session Management | Redis Cluster | Horizontal scaling, pub/sub, fast access |
| Agent Distribution | Task Queue + Agent Pool | Load balancing, quota enforcement, autoscaling |
| Database | PostgreSQL | ACID compliance, JSON support, row-level security |

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│         Web Frontend | Mobile Apps | REST Clients                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      GATEWAY LAYER                               │
│   Load Balancer → WebSocket Gateway → REST API Gateway          │
│   (Authentication, Session Management, Request Routing)          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    CORE SERVICES                                 │
│   OAuth2/JWT Auth | Session Manager (Redis) | Request Router    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                  AGENT DISTRIBUTION                              │
│   Agent Dispatcher → Task Queue (Redis) → Agent Pool Manager    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    AGENT RUNTIME                                 │
│   Agent Instance 1 | Agent Instance 2 | ... | Agent Instance N  │
│   (LLM Client, Skills, Memory, MCP Tools)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      DATA LAYER                                  │
│        Redis Cluster (Sessions/Queue) | PostgreSQL (Data)       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow: Client → Gateway → Agent → Response

```
1. CONNECTION ESTABLISHMENT
   Client → Load Balancer → WebSocket Gateway
   → OAuth2/JWT Auth → Redis Session → Connected

2. CHAT REQUEST FLOW
   Client → WebSocket Gateway → Auth Verification
   → Session Update → Agent Dispatcher → Task Queue
   → Agent Pool → Agent Execution → LLM + Skills
   → Result Stream → Gateway → Client

3. RESPONSE STREAMING
   Agent → Task Queue (chunks) → Gateway → Redis Pub/Sub
   → All connected clients → WebSocket → Client
```

### 2.3 Deployment Topology (1,000 Concurrent Users)

```
Cloud Infrastructure (AWS/GCP)
├── Edge Layer
│   ├── CDN (Static Assets)
│   └── WAF (Security)
├── Load Balancing
│   └── Application Load Balancer (WebSocket-aware)
├── Compute Layer
│   ├── Gateway Pods (3-5 instances, ~300 connections each)
│   └── Agent Pods (5-10 instances, 100 exec/min)
└── Data Layer
    ├── Redis Cluster (3M + 3R, Pub/Sub + Sessions + Queue)
    ├── PostgreSQL Primary (Writes)
    └── PostgreSQL Replicas x2 (Reads)
```

**Scaling Calculations:**

| Component | Configuration | Rationale |
|-----------|---------------|-----------|
| WebSocket Gateways | 3-5 instances | Each handles ~300 connections |
| Agent Pods | 5-10 instances | 100 exec/min = 1.67/sec, ~20s/exec = 33 concurrent |
| Redis Cluster | 3M + 3R | Pub/sub + session + queue |
| PostgreSQL | 1P + 2R | Write master + read replicas |

---

## 3. Gateway Layer Design

### 3.1 WebSocket Protocol Specification

**Message Protocol:**

```typescript
// Request Messages
interface WSRequest {
  type: 'chat' | 'ping' | 'abort' | 'typing';
  client_id: string;
  payload: ChatPayload | PingPayload;
}

interface ChatPayload {
  app_id: string;
  message: string;
  conversation_id?: string;
  stream?: boolean;
}

// Response Messages
interface WSResponse {
  type: 'accepted' | 'chunk' | 'response' | 'error' | 'pong' | 'typing' | 'thinking';
  task_id?: string;
  data: any;
  timestamp: string;
}
```

### 3.2 OAuth2 + JWT Authentication Flow

```
1. User clicks "Login" → Frontend redirects to OAuth provider
2. OAuth provider authenticates → Returns authorization code
3. Frontend exchanges code for tokens (access_token, refresh_token)
4. Frontend connects to WebSocket with JWT token
5. Gateway validates JWT → Creates Redis session → Connected

JWT Token Structure:
{
  "sub": "user_id",
  "tenant_id": "tenant_abc",
  "roles": ["developer"],
  "permissions": ["app:read", "app:execute"],
  "exp": 1709673600,
  "iat": 1709670000
}
```

### 3.3 Session Management with Redis

```
Redis Key Structure:
- session:{tenant_id}:{client_id} → Session data (TTL: 24h)
- tenant:{tenant_id}:sessions → Set of active sessions
- tenant:{tenant_id}:broadcast → Pub/Sub channel
- client:{client_id}:response → Response channel

Session Data:
{
  "tenant_id": "tenant_abc",
  "client_id": "client_xyz",
  "user_id": "user_123",
  "app_id": "app_001",
  "connected_at": "2026-03-05T10:00:00Z",
  "state": "active"
}
```

### 3.4 Request Routing Logic

```
1. Validate message type
2. Check tenant status (active/suspended)
3. Verify rate limits (per-tenant, per-user)
4. Check concurrency limits (max sessions)
5. Route to agent dispatcher
6. Return task_id for tracking
```

---

## 4. Agent Distribution System

### 4.1 Agent Dispatcher

```
Request Flow:
┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│ Request │ → │ Validate │ → │ Quota   │ → │ Select   │
│         │    │ Tenant   │    │ Check   │    │ Agent    │
└─────────┘    └──────────┘    └─────────┘    └──────────┘
                                                    │
┌─────────┐    ┌──────────┐    ┌─────────┐         │
│ Return  │ ← │ Notify   │ ← │ Enqueue │ ←────────┘
│ Task ID │    │ Agent    │    │ Task    │
└─────────┘    └──────────┘    └─────────┘
```

### 4.2 Agent Pool Management

```
Agent Instance States:
- STARTING: Agent initializing
- READY: Available for tasks
- BUSY: Currently executing
- IDLE: No tasks, waiting
- STOPPING: Shutting down
- ERROR: Failed state

Auto-Scaling Rules:
- Scale Up: When 80% agents are BUSY
- Scale Down: When agents IDLE > 5 minutes
- Min Size: 2 agents per tenant
- Max Size: 10 agents per tenant (enterprise plan)
```

### 4.3 Load Balancing Strategies

| Strategy | Algorithm | Best For |
|----------|-----------|----------|
| Round Robin | Sequential rotation | Homogeneous agents |
| Least Connections | Min task count | Varying task duration |
| Weighted | Capacity-based | Heterogeneous instances |
| Priority | Priority queue | Tiered service plans |

---

## 5. Multi-Tenant Architecture

### 5.1 Database Schema Design

```
┌─────────────┐       ┌─────────────┐
│   Tenant    │───1:N─│    User     │
│             │       │             │
│ id          │       │ tenant_id   │
│ name        │       │ email       │
│ slug        │       │ roles       │
│ plan        │       └─────────────┘
│ is_active   │
└─────────────┘
       │
       │1:N
       ▼
┌─────────────┐       ┌─────────────┐
│ Application │───1:N─│Conversation │
│             │       │             │
│ tenant_id   │       │ tenant_id   │
│ name        │       │ app_id      │
│ schema      │       │ user_id     │
└─────────────┘       └─────────────┘
                              │
                              │1:N
                              ▼
                       ┌─────────────┐
                       │   Message   │
                       │             │
                       │ conversation_id
                       │ role        │
                       │ content     │
                       └─────────────┘
```

### 5.2 Tenant Resource Quotas

| Plan | Max Sessions | Max Agents | Monthly Tokens | Monthly Requests |
|------|--------------|------------|----------------|------------------|
| Free | 10 | 2 | 100K | 1K |
| Pro | 100 | 10 | 2M | 50K |
| Enterprise | 1,000 | 50 | Unlimited | Unlimited |

### 5.3 Row-Level Security (PostgreSQL)

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY tenant_isolation ON applications
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

---

## 6. Security Model

### 6.1 Authentication Layers

```
1. OAuth2 Provider (External)
   - User authentication
   - Token generation

2. JWT Validation (Gateway)
   - Signature verification
   - Expiration check
   - Tenant context extraction

3. API Key Validation (Service-to-Service)
   - Hash verification
   - Scope validation
   - Rate limiting
```

### 6.2 RBAC Permission Matrix

| Role | Tenant | App | Key | User |
|------|--------|-----|-----|------|
| Super Admin | CRUD | CRUD | CRUD | CRUD |
| Tenant Admin | R/U | CRUD | CRUD | CRUD |
| Developer | R | CRUD | - | R |
| User | R | R/E | - | R |
| Viewer | R | R | - | R |

### 6.3 Security Checklist

- [ ] JWT token validation on every request
- [ ] Tenant context in all database queries
- [ ] Rate limiting per tenant/user
- [ ] API key scope validation
- [ ] Audit logging for sensitive operations
- [ ] Encrypted secrets in database
- [ ] HTTPS only for all endpoints
- [ ] WebSocket connection authentication

---

## 7. Technology Stack

### 7.1 Core Technologies

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| API Framework | FastAPI | 0.109+ | REST + WebSocket |
| ASGI Server | Uvicorn | 0.27+ | Production server |
| Database | PostgreSQL | 15+ | Primary storage |
| ORM | SQLAlchemy | 2.0+ | Async ORM |
| Cache/Queue | Redis | 7+ | Sessions, pub/sub, queue |
| LLM Integration | LiteLLM | 1.20+ | Multi-provider |
| Auth | python-jose | latest | JWT + OAuth2 |
| Rate Limiting | slowapi | latest | Per-tenant limits |
| Validation | Pydantic | 2.5+ | Request validation |
| Container | Docker | - | Deployment |
| Orchestration | Kubernetes | 1.28+ | Scaling |

### 7.2 Redis Configuration

```
Database Layout:
- DB 0: Session storage
- DB 1: Pub/Sub channels
- DB 2: Task queue
- DB 3: Rate limiting counters

Key Patterns:
- session:{tenant_id}:{client_id}
- tenant:{tenant_id}:sessions
- task:queue:{tenant_id}:{priority}
- rate:{tenant_id}:{user_id}:{endpoint}
```

---

## 8. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Create Tenant model + migration | 1 day | Tenant table |
| Add tenant_id to all tables | 1 day | Schema migration |
| Implement tenant context middleware | 2 days | Request context |
| Set up Row-Level Security | 1 day | RLS policies |
| Create User model + OAuth fields | 1 day | User table |

**Deliverables:** Multi-tenant data model with RLS

### Phase 2: Authentication (Weeks 2-3)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Implement JWT validation | 2 days | JWT middleware |
| Create OAuth2 flow endpoints | 2 days | OAuth integration |
| Build API key CRUD | 2 days | API key management |
| Add RBAC permission system | 2 days | Role-based access |
| Deprecate master-key auth | 1 day | Secure auth |

**Deliverables:** OAuth2 + JWT + RBAC

### Phase 3: Gateway (Weeks 3-4)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Implement Redis session store | 2 days | Session persistence |
| Refactor WebSocket gateway | 3 days | Production gateway |
| Add connection heartbeat | 1 day | Health monitoring |
| Implement message protocol | 2 days | Typed protocol |
| Configure Nginx load balancer | 1 day | Load balancing |

**Deliverables:** Redis-backed WebSocket gateway

### Phase 4: Agent Distribution (Weeks 4-5)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Build Redis task queue | 2 days | Task queue |
| Create Agent pool manager | 2 days | Pool management |
| Implement agent dispatcher | 2 days | Request routing |
| Add load balancing strategies | 1 day | Load balancing |
| Implement quota enforcement | 2 days | Quota system |

**Deliverables:** Agent pool with task queue

### Phase 5: Enterprise Features (Weeks 5-6)

| Task | Effort | Deliverable |
|------|--------|-------------|
| Implement rate limiting | 2 days | Per-tenant limits |
| Add audit logging | 2 days | Audit trail |
| Build monitoring hooks | 2 days | Metrics endpoints |
| Add graceful shutdown | 1 day | Safe shutdown |
| Configure auto-scaling | 2 days | K8s HPA |

**Deliverables:** Production-ready enterprise platform

### Timeline

```
Week 1-2: Phase 1 (Foundation)
Week 2-3: Phase 2 (Authentication)
Week 3-4: Phase 3 (Gateway)
Week 4-5: Phase 4 (Agent Distribution)
Week 5-6: Phase 5 (Enterprise Features)
Total: 10 weeks to production-ready
```

---

## 9. Monitoring Hooks (Future Phase)

### Prometheus Metrics

```
- websocket_connections{tenant_id}
- http_requests_total{method, endpoint, status, tenant_id}
- agent_executions_total{tenant_id, app_id, status}
- agent_execution_duration_seconds{tenant_id, app_id}
- task_queue_depth{tenant_id, priority}
- active_agents{tenant_id, status}
```

---

## 10. Next Steps

1. **Review**: Architecture team reviews this document
2. **Approve**: Sign-off on architectural decisions
3. **Plan**: Create detailed sprint backlog for Phase 1
4. **Implement**: Begin Phase 1 development

---

**Document Status**: Complete  
**Ready for**: Architecture Review  
**Implementation**: Pending Approval
