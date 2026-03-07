# Architecture Diagrams

This document contains visual representations of the SmartLink platform architecture using Mermaid diagrams.

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Data Flow Diagram](#2-data-flow-diagram)
3. [Authentication Flow](#3-authentication-flow)
4. [WebSocket Protocol](#4-websocket-protocol)
5. [Agent Distribution Flow](#5-agent-distribution-flow)
6. [Multi-Tenant Data Model](#6-multi-tenant-data-model)
7. [Deployment Topology](#7-deployment-topology)
8. [Security Architecture](#8-security-architecture)

---

## 1. System Architecture

High-level component view showing the layered architecture and major subsystems.

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        WebApp["Web Application<br/>(React/Vue)"]
        MobileApp["Mobile App<br/>(iOS/Android)"]
        CLI["CLI Tool<br/>(Python/Go)"]
        ExternalAPI["External API Clients"]
    end

    subgraph Gateway["Gateway Layer"]
        APIRouter["API Router<br/>(FastAPI)"]
        WSGateway["WebSocket Gateway"]
        RateLimiter["Rate Limiter<br/>(Redis)"]
        AuthMW["Auth Middleware"]
        CorsMW["CORS Middleware"]
    end

    subgraph Core["Core Services"]
        AppSvc["Application Service"]
        ResourceSvc["Resource Service"]
        ConvSvc["Conversation Service"]
        ConfigSvc["Configuration Service"]
    end

    subgraph Distribution["Agent Distribution"]
        Router["Task Router"]
        LoadBalancer["Load Balancer"]
        Scheduler["Task Scheduler"]
        HealthChecker["Health Checker"]
    end

    subgraph Runtime["Agent Runtime"]
        Orchestrator["Workflow Orchestrator"]
        LLMClient["LLM Client<br/>(LiteLLM)"]
        SkillRegistry["Skill Registry"]
        MCPClient["MCP Client"]
    end

    subgraph Infrastructure["Infrastructure"]
        Postgres[(PostgreSQL)]
        Redis[(Redis Cache)]
        MessageQueue["Message Queue<br/>(Redis/RabbitMQ)"]
        ObjectStore["Object Storage<br/>(S3/MinIO)"]
    end

    WebApp --> APIRouter
    MobileApp --> APIRouter
    CLI --> APIRouter
    ExternalAPI --> APIRouter
    WebApp -.->|"Realtime"| WSGateway
    MobileApp -.->|"Realtime"| WSGateway

    APIRouter --> RateLimiter
    APIRouter --> AuthMW
    APIRouter --> CorsMW
    WSGateway --> AuthMW

    RateLimiter --> AppSvc
    AuthMW --> AppSvc

    AppSvc --> ConfigSvc
    AppSvc --> ConvSvc
    AppSvc --> ResourceSvc

    ConvSvc --> Router
    AppSvc --> Router

    Router --> LoadBalancer
    Router --> Scheduler
    LoadBalancer --> HealthChecker

    Scheduler --> Orchestrator
    LoadBalancer --> Orchestrator

    Orchestrator --> LLMClient
    Orchestrator --> SkillRegistry
    Orchestrator --> MCPClient

    AppSvc --> Postgres
    ResourceSvc --> Postgres
    ConvSvc --> Postgres
    ConfigSvc --> Postgres

    RateLimiter --> Redis
    HealthChecker --> Redis
    MessageQueue --> Redis

    ResourceSvc --> ObjectStore
    ConvSvc --> ObjectStore

    style Client fill:#e3f2fd
    style Gateway fill:#fff3e0
    style Core fill:#e8f5e9
    style Distribution fill:#fce4ec
    style Runtime fill:#f3e5f5
    style Infrastructure fill:#ffebee
```

### Component Descriptions

| Layer | Component | Purpose |
|-------|-----------|---------|
| Client | WebApp, MobileApp, CLI | User-facing applications and tools |
| Gateway | APIRouter, WSGateway | Entry points with routing and protocol handling |
| Core | Application, Resource, Conversation Services | Business logic and domain operations |
| Distribution | Router, Load Balancer | Task allocation and agent selection |
| Runtime | Orchestrator, LLM Client | AI agent execution and LLM integration |
| Infrastructure | Database, Cache, Storage | Persistent and ephemeral data stores |

---

## 2. Data Flow Diagram

Request and response flow through the system, showing how a typical API call is processed.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant G as API Gateway
    participant A as Auth Middleware
    participant S as Application Service
    participant O as Orchestrator
    participant L as LLM Provider
    participant DB as PostgreSQL
    participant Cache as Redis

    C->>G: POST /api/v1/applications/{id}/run<br/>X-API-Key: {api_key}

    G->>A: Validate API Key
    A->>A: Compare against MASTER_API_KEY

    alt Invalid API Key
        A-->>G: 403 Forbidden
        G-->>C: Invalid API key
    else Valid Key
        A-->>G: Continue
    end

    G->>S: Route to handler

    S->>DB: Load application by ID
    DB-->>S: Application config (schema, skills)

    S->>DB: Get or create conversation
    DB-->>S: Conversation record

    S->>DB: Persist user message
    S->>DB: INSERT message (role=user)

    S->>O: Execute workflow<br/>app_id, input_data, conversation_id

    O->>DB: Load conversation history
    O->>DB: SELECT messages ORDER BY created_at
    DB-->>O: Message history list

    O->>O: Build available tools<br/>from skill_registry

    O->>L: chat.completions.create()<br/>messages + tools

    L-->>O: Streaming response chunks

    loop For each chunk
        O-->>S: Yield chunk
        S-->>G: Stream response
        G-->>C: SSE/JSON chunk
    end

    O-->>S: Complete response

    S->>DB: INSERT assistant message
    S->>DB: UPDATE conversation timestamp

    S-->>G: 200 OK + final response
    G-->>C: JSON response with result
```

### Flow Stages

1. **Ingress**: Client sends request with X-API-Key header
2. **Authentication**: API key validated against MASTER_API_KEY
3. **Routing**: Request routed to Application Service handler
4. **Validation**: Application loaded and validated
5. **Persistence**: User message stored in database
6. **Execution**: Orchestrator processes with conversation context
7. **LLM Call**: LiteLLM routes to configured provider
8. **Streaming**: Response chunks returned via streaming
9. **Persistence**: Assistant response stored
10. **Response**: Final result returned to client

---

## 3. Authentication Flow

API Key-based authentication flow. Currently implements master API key validation with support for per-key permissions.

```mermaid
flowchart LR
    subgraph Client["Client Application"]
        User["User/Developer"]
        App["App Client"]
    end

    subgraph Gateway["API Gateway"]
        APIGW["FastAPI Gateway"]
        AuthMW["API Key Middleware<br/>gateway/middleware/auth.py"]
        CorsMW["CORS Middleware"]
    end

    subgraph Validation["Key Validation"]
        CheckHeader["Extract X-API-Key Header"]
        VerifyKey["verify_api_key()<br/>core/security.py"]
        CheckPublic{"Public Path?"}
    end

    subgraph Storage["Storage"]
        MasterKey[(Master Key<br/>env: MASTER_API_KEY)]
        APIKeyDB[(API Key Table<br/>models/application.py)]
    end

    subgraph Backend["Backend Services"]
        AppSvc["Application Service"]
        ResourceSvc["Resource Service"]
    end

    %% API Key Flow
    User -->|"1. Generate API Key"| App
    App -->|"2. Request with X-API-Key"| APIGW
    APIGW -->|"3. Check path"| CheckPublic
    CheckPublic -->|"Public<br/>/, /health, /docs"| CorsMW
    CheckPublic -->|"Protected"| AuthMW
    
    AuthMW -->|"4. Extract header"| CheckHeader
    CheckHeader -->|"5. Validate"| VerifyKey
    
    VerifyKey -->|"6a. Check master key"| MasterKey
    VerifyKey -->|"6b. Check database"| APIKeyDB
    
    MasterKey -->|"7a. Valid"| CorsMW
    APIKeyDB -->|"7b. Valid + permissions"| CorsMW
    
    CorsMW -->|"8. Route to handler"| AppSvc
    AppSvc -->|"9. CRUD Operations"| ResourceSvc
    
    %% WebSocket Flow
    App -.->|"WS: api_key query param"| APIGW
    APIGW -.->|"verify_api_key_ws()"| VerifyKey

    style Client fill:#e3f2fd
    style Gateway fill:#fff3e0
    style Validation fill:#e8f5e9
    style Storage fill:#ffebee
    style Backend fill:#fce4ec
```

### Authentication Methods

| Method | Use Case | Location | Implementation |
|--------|----------|----------|----------------|
| Master API Key | Development, admin access | Environment variable | `MASTER_API_KEY` in `.env` |
| Database API Key | Per-application keys | PostgreSQL | `APIKey` model |
| WebSocket Key | Real-time connections | Query param or header | `verify_api_key_ws()` |

### Public Paths (No Auth Required)

```python
PUBLIC_PATHS = {
    "/",           # Root
    "/health",     # Health check
    "/docs",       # Swagger UI
    "/redoc",      # ReDoc
    "/openapi.json",
    "/metrics",
    "/ws*",        # WebSocket (auth handled separately)
    "/static*"
}
```

### API Key Header

```http
GET /api/v1/applications HTTP/1.1
Host: localhost:8000
X-API-Key: sk-smartlink-master-key-change-in-production
```

### Future Enhancements

| Feature | Status | Planned For |
|---------|--------|-------------|
| OAuth2 / OpenID Connect | Not implemented | v2.0 |
| JWT Tokens | Not implemented | v2.0 |
| Role-Based Access Control | Partial | v1.5 |
| API Key expiration | Partial | v1.2 |
| Token refresh | Not implemented | v2.0 |

---

## 4. WebSocket Protocol

Real-time bidirectional communication protocol for streaming responses.

```mermaid
sequenceDiagram
    autonumber
    participant Client as WebSocket Client
    participant GW as WebSocket Gateway
    participant Auth as Auth Handler
    participant Conv as Conversation Service
    participant Orchestrator as Agent Orchestrator
    participant LLM as LLM Provider
    participant PubSub as Redis Pub/Sub

    %% Connection Establishment
    Client->>GW: wss://api.smartlink.io/ws/v1/chat
    GW->>Auth: Validate connection token
    Auth-->>GW: User authenticated (user_id, tenant_id)
    GW-->>Client: {"type": "connected", "connection_id": "..."}

    %% Subscribe to Conversation
    Client->>GW: {"type": "subscribe", "conversation_id": "conv_123"}
    GW->>Conv: Validate conversation access
    Conv-->>GW: Access granted
    GW->>PubSub: SUBSCRIBE stream:conv_123
    GW-->>Client: {"type": "subscribed", "conversation_id": "conv_123"}

    %% Send Message
    Client->>GW: {<br/>  "type": "message",<br/>  "conversation_id": "conv_123",<br/>  "content": "Hello!",<br/>  "metadata": {}<br/>}
    
    GW->>Conv: Process message
    Conv->>Conv: Persist user message
    Conv->>Orchestrator: Submit task
    
    GW-->>Client: {<br/>  "type": "message_ack",<br/>  "message_id": "msg_456",<br/>  "status": "processing"<br/>}

    %% Streaming Response
    Orchestrator->>LLM: Request streaming completion
    
    loop Streaming Chunks
        LLM-->>Orchestrator: Content chunk
        Orchestrator->>PubSub: PUBLISH stream:conv_123 chunk
        PubSub-->>GW: Receive chunk
        GW-->>Client: {<br/>  "type": "stream_chunk",<br/>  "conversation_id": "conv_123",<br/>  "content": "chunk text",<br/>  "chunk_index": N<br/>}
    end

    Orchestrator-->>Conv: Final response
    Conv->>Conv: Persist assistant message
    
    GW-->>Client: {<br/>  "type": "stream_end",<br/>  "conversation_id": "conv_123",<br/>  "message_id": "msg_789",<br/>  "usage": {<br/>    "prompt_tokens": 100,<br/>    "completion_tokens": 50<br/>  }<br/>}

    %% Error Handling
    Note over Client,GW: Error Scenarios
    
    alt Authentication Failed
        GW-->>Client: {<br/>  "type": "error",<br/>  "code": "AUTH_FAILED",<br/>  "message": "Invalid token"<br/>}
        GW->>GW: Close connection
    else Rate Limited
        GW-->>Client: {<br/>  "type": "error",<br/>  "code": "RATE_LIMITED",<br/>  "retry_after": 60<br/>}
    else LLM Error
        Orchestrator-->>PubSub: PUBLISH error
        PubSub-->>GW: Error event
        GW-->>Client: {<br/>  "type": "error",<br/>  "code": "LLM_ERROR",<br/>  "message": "Provider unavailable"<br/>}
    end

    %% Disconnection
    Client->>GW: {"type": "unsubscribe", "conversation_id": "conv_123"}
    GW->>PubSub: UNSUBSCRIBE stream:conv_123
    GW-->>Client: {"type": "unsubscribed"}
    
    Client->>GW: Close connection
    GW->>GW: Cleanup subscriptions
    GW->>Conv: Mark connection closed
```

### Message Types

| Type | Direction | Description |
|------|-----------|-------------|
| `connected` | Server->Client | Connection established |
| `subscribe` | Client->Server | Subscribe to conversation stream |
| `subscribed` | Server->Client | Subscription confirmed |
| `message` | Client->Server | Send chat message |
| `message_ack` | Server->Client | Message received acknowledgment |
| `stream_chunk` | Server->Client | Partial LLM response |
| `stream_end` | Server->Client | Streaming complete |
| `error` | Server->Client | Error notification |
| `ping/pong` | Bidirectional | Keep-alive heartbeat |
| `unsubscribe` | Client->Server | Stop receiving updates |

### Connection Lifecycle

1. **Connect**: WebSocket handshake with JWT in query param or header
2. **Subscribe**: Join conversation-specific channels
3. **Interact**: Send messages, receive streaming responses
4. **Disconnect**: Graceful close or timeout cleanup

---

## 5. Agent Distribution Flow

Task routing and agent selection for distributed execution.

```mermaid
flowchart TB
    subgraph Incoming["Task Queue"]
        Queue[(Priority Queue)]
        Task["Task:<br/>conversation_id<br/>priority: high<br/>agent_type: chatbot"]
    end

    subgraph Router["Task Router"]
        Parser["Task Parser"]
        Strategy["Strategy Selector"]
        Rules{"Routing Rules"}
    end

    subgraph Selection["Agent Selection"]
        Filter["Filter by:<br/>- Capabilities<br/>- Tenant isolation<br/>- Load"]
        Score["Score Agents:<br/>- Availability<br/>- Latency<br/>- Success rate"]
        Pick["Select Best Match"]
    end

    subgraph Agents["Agent Pool"]
        Agent1["Agent-1<br/>Status: idle<br/>Load: 0%"]
        Agent2["Agent-2<br/>Status: busy<br/>Load: 75%"]
        Agent3["Agent-3<br/>Status: idle<br/>Load: 10%"]
        AgentN["Agent-N<br/>Status: idle<br/>Load: 5%"]
    end

    subgraph Execution["Execution"]
        Orchestrator["Workflow Orchestrator"]
        Result["Result Handler"]
    end

    Task --> Queue
    Queue --> Parser
    
    Parser --> Strategy
    Strategy --> Rules
    
    Rules -->|"Simple chat"| Filter
    Rules -->|"Complex workflow"| Filter
    Rules -->|"Urgent"| Filter
    
    Filter --> Score
    Score --> Pick
    
    Pick --> Agent1
    Pick --> Agent2
    Pick --> Agent3
    Pick --> AgentN
    
    Agent1 --> Orchestrator
    Agent2 -.->|"Skipped: busy"| Queue
    Agent3 --> Orchestrator
    AgentN -.->|"Not selected"| Queue
    
    Orchestrator --> Result
    Result -->|"Success"| Queue
    Result -->|"Retry"| Queue
    Result -->|"Failed"| DLQ[(Dead Letter Queue)]

    style Incoming fill:#e3f2fd
    style Router fill:#fff3e0
    style Selection fill:#e8f5e9
    style Agents fill:#f3e5f5
    style Execution fill:#fce4ec
```

### Routing Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Round Robin** | Distribute evenly across agents | General load balancing |
| **Least Loaded** | Route to agent with lowest CPU/memory | CPU-intensive tasks |
| **Capability Match** | Match task requirements to agent skills | Specialized workflows |
| **Tenant Affinity** | Prefer agents already handling tenant's data | Data locality |
| **Geographic** | Route to nearest agent | Latency-sensitive tasks |
| **Priority** | High-priority tasks jump queue | Urgent requests |

### Agent Selection Algorithm

```python
score = (
    availability_weight * (1 - agent.current_load) +
    latency_weight * (1 / agent.average_latency) +
    success_weight * agent.success_rate +
    affinity_weight * (1 if agent.tenant == task.tenant else 0) +
    capability_weight * agent.capability_match(task.requirements)
)
```

### Failure Handling

1. **Retry**: Up to 3 attempts with exponential backoff
2. **Circuit Breaker**: Temporarily disable failing agents
3. **Dead Letter Queue**: Persist failed tasks for analysis
4. **Failover**: Automatic agent replacement

---

## 6. Multi-Tenant Data Model

Entity relationships for tenant-isolated data architecture.

```mermaid
erDiagram
    TENANT ||--o{ USER : contains
    TENANT ||--o{ APPLICATION : owns
    TENANT ||--o{ API_KEY : issues
    USER ||--o{ CONVERSATION : creates
    USER ||--o{ MESSAGE : sends
    APPLICATION ||--o{ CONVERSATION : hosts
    APPLICATION ||--o{ RESOURCE : manages
    APPLICATION ||--o{ WORKFLOW : defines
    CONVERSATION ||--o{ MESSAGE : contains
    WORKFLOW ||--o{ WORKFLOW_NODE : consists_of
    WORKFLOW ||--o{ WORKFLOW_EDGE : defines
    RESOURCE ||--o{ RESOURCE_VERSION : versions
    APPLICATION ||--o{ CONFIGURATION : has

    TENANT {
        uuid id PK
        string name
        string slug UK
        string status
        datetime created_at
        datetime updated_at
        jsonb settings
        string billing_plan
    }

    USER {
        uuid id PK
        uuid tenant_id FK
        string email UK
        string password_hash
        string full_name
        string role
        boolean is_active
        datetime last_login
        jsonb preferences
    }

    API_KEY {
        uuid id PK
        uuid tenant_id FK
        string key_hash UK
        string name
        string[] scopes
        datetime expires_at
        datetime last_used
        boolean is_active
    }

    APPLICATION {
        uuid id PK
        uuid tenant_id FK
        string name
        string description
        string status
        jsonb config
        datetime created_at
        uuid created_by FK
    }

    CONFIGURATION {
        uuid id PK
        uuid application_id FK
        string key UK
        string value
        boolean is_encrypted
        datetime created_at
    }

    RESOURCE {
        uuid id PK
        uuid application_id FK
        string name
        string type
        string mime_type
        int64 size_bytes
        string storage_path
        jsonb metadata
        datetime created_at
    }

    RESOURCE_VERSION {
        uuid id PK
        uuid resource_id FK
        int version_number
        string storage_path
        int64 size_bytes
        datetime created_at
    }

    CONVERSATION {
        uuid id PK
        uuid application_id FK
        uuid user_id FK
        string title
        string status
        jsonb context
        datetime last_activity
        datetime created_at
    }

    MESSAGE {
        uuid id PK
        uuid conversation_id FK
        uuid user_id FK
        string role
        string content
        jsonb metadata
        jsonb usage_stats
        datetime created_at
        int sequence_number
    }

    WORKFLOW {
        uuid id PK
        uuid application_id FK
        string name
        string description
        jsonb trigger_config
        boolean is_active
        datetime created_at
    }

    WORKFLOW_NODE {
        uuid id PK
        uuid workflow_id FK
        string node_type
        string node_id
        jsonb config
        int position_x
        int position_y
    }

    WORKFLOW_EDGE {
        uuid id PK
        uuid workflow_id FK
        string source_node_id
        string target_node_id
        string condition
    }
```

### Tenant Isolation Strategy

| Level | Implementation | Description |
|-------|---------------|-------------|
| **Database** | Schema per tenant | Separate schemas for strict isolation |
| **Row-Level** | tenant_id column | Single schema with tenant filtering |
| **Application** | Middleware filtering | Query filtering in service layer |

### Key Relationships

1. **Tenant -> Users**: One-to-many, users belong to exactly one tenant
2. **Tenant -> Applications**: One-to-many, applications are tenant-scoped
3. **Application -> Conversations**: One-to-many, conversations belong to one app
4. **Conversation -> Messages**: One-to-many, ordered by sequence_number
5. **User -> Conversations**: One-to-many, track conversation ownership
6. **Application -> Resources**: One-to-many, file attachments per app
7. **Application -> Workflows**: One-to-many, workflow definitions per app

### Indexing Strategy

```sql
-- Tenant-scoped queries
CREATE INDEX idx_app_tenant ON applications(tenant_id);
CREATE INDEX idx_conv_app_user ON conversations(application_id, user_id);
CREATE INDEX idx_msg_conv_seq ON messages(conversation_id, sequence_number);

-- Full-text search
CREATE INDEX idx_msg_content_search ON messages USING gin(to_tsvector('english', content));

-- Time-series queries
CREATE INDEX idx_conv_last_activity ON conversations(last_activity DESC);
```

---

## 7. Deployment Topology

Infrastructure layout for production deployment.

```mermaid
flowchart TB
    subgraph DNS["DNS & CDN"]
        Cloudflare["Cloudflare<br/>DNS + WAF + CDN"]
        Route53["Route 53<br/>(Health Checks)"]
    end

    subgraph Edge["Edge Layer"]
        LB1["Load Balancer 1<br/>(Nginx/ALB)"]
        LB2["Load Balancer 2<br/>(Failover)"]
        CDN["CDN Edge<br/>(Static Assets)"]
    end

    subgraph K8s["Kubernetes Cluster"]
        subgraph Ingress["Ingress Layer"]
            IngressCtrl["Ingress Controller<br/>(NGINX)"]
            CertMgr["Cert Manager<br/>(Let's Encrypt)"]
        end

        subgraph API["API Tier"]
            API1["API Pod 1"]
            API2["API Pod 2"]
            APIN["API Pod N"]
            HPA["Horizontal Pod Autoscaler"]
        end

        subgraph Workers["Worker Tier"]
            Worker1["Agent Worker 1"]
            Worker2["Agent Worker 2"]
            WorkerN["Agent Worker N"]
        end

        subgraph Background["Background Jobs"]
            Scheduler["Task Scheduler"]
            Cleaner["Cleanup Worker"]
        end
    end

    subgraph Data["Data Layer"]
        subgraph PostgresCluster["PostgreSQL Cluster"]
            PGPrimary["Primary<br/>(Writes)"]
            PGReplica1["Replica 1<br/>(Reads)"]
            PGReplica2["Replica 2<br/>(Reads)"]
        end

        subgraph RedisCluster["Redis Cluster"]
            RedisMaster["Master"]
            RedisReplica["Replica"]
            RedisSentinel["Sentinel<br/>(HA)"]
        end

        S3["Object Storage<br/>(S3/MinIO)"]
    end

    subgraph Monitoring["Observability"]
        Prometheus["Prometheus"]
        Grafana["Grafana"]
        ELK["ELK Stack<br/>(Logs)"]
        Jaeger["Jaeger<br/>(Tracing)"]
    end

    subgraph Security["Security"]
        Vault["HashiCorp Vault<br/>(Secrets)"]
        WAF["Web Application Firewall"]
    end

    Cloudflare --> LB1
    Cloudflare -.->|"Failover"| LB2
    Route53 --> Cloudflare
    
    LB1 --> IngressCtrl
    LB2 -.-> IngressCtrl
    CDN -.->|"Static assets"| S3
    
    IngressCtrl --> API1
    IngressCtrl --> API2
    IngressCtrl --> APIN
    HPA --> API1
    HPA --> API2
    HPA --> APIN
    
    API1 --> Worker1
    API2 --> Worker2
    APIN --> WorkerN
    
    API1 --> Scheduler
    API1 --> Cleaner
    
    API1 --> PGPrimary
    API2 --> PGPrimary
    Worker1 --> PGReplica1
    Worker2 --> PGReplica2
    
    API1 --> RedisMaster
    Worker1 --> RedisMaster
    Scheduler --> RedisMaster
    
    API1 --> S3
    Worker1 --> S3
    
    API1 -.->|"Metrics"| Prometheus
    API2 -.->|"Metrics"| Prometheus
    Worker1 -.->|"Metrics"| Prometheus
    
    Prometheus --> Grafana
    API1 -.->|"Logs"| ELK
    API1 -.->|"Traces"| Jaeger
    
    API1 -.->|"Secrets"| Vault
    Worker1 -.->|"Secrets"| Vault

    style DNS fill:#e3f2fd
    style Edge fill:#fff3e0
    style K8s fill:#e8f5e9
    style Data fill:#fce4ec
    style Monitoring fill:#f3e5f5
    style Security fill:#ffebee
```

### Resource Specifications

| Component | Replicas | CPU | Memory | Storage |
|-----------|----------|-----|--------|---------|
| API Pods | 3-10 (auto) | 1 core | 2 GB | - |
| Agent Workers | 2-20 (auto) | 2 cores | 4 GB | - |
| PostgreSQL Primary | 1 | 4 cores | 8 GB | 500 GB SSD |
| PostgreSQL Replicas | 2 | 2 cores | 4 GB | 500 GB SSD |
| Redis | 3 | 1 core | 2 GB | - |
| Background Workers | 2 | 1 core | 2 GB | - |

### Scaling Policies

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU > 70% | 2 minutes | Scale up +1 pod |
| CPU < 30% | 5 minutes | Scale down -1 pod |
| Queue depth > 100 | Immediate | Scale workers +5 |
| Response time > 500ms | 1 minute | Alert + scale |

### Backup Strategy

| Data | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| PostgreSQL | Hourly | 30 days | Cross-region S3 |
| PostgreSQL | Daily | 1 year | Cold storage |
| Redis | Continuous | 24 hours | AOF + RDB |
| Object Storage | Versioned | 90 days | Same region |

---

## 8. Security Architecture

Defense in depth with multiple security layers.

```mermaid
flowchart TB
    subgraph Perimeter["Perimeter Security"]
        DDoS["DDoS Protection<br/>(Cloudflare/AWS Shield)"]
        WAF["Web Application Firewall<br/>(OWASP Rules)"]
        IPFilter["IP Allowlist/Denylist"]
        GeoBlock["Geographic Blocking"]
    end

    subgraph Transport["Transport Security"]
        TLS["TLS 1.3<br/>(Certificate pinning)"]
        MTLS["mTLS<br/>(Service mesh)"]
        CertMgmt["Certificate Management<br/>(Let's Encrypt)"]
    end

    subgraph AuthN["Authentication Layer"]
        OAuth["OAuth2 / OpenID Connect"]
        JWTVal["JWT Validation"]
        APIKey["API Key Verification"]
        MFACheck["MFA Enforcement"]
    end

    subgraph AuthZ["Authorization Layer"]
        RBAC["Role-Based Access Control"]
        ABAC["Attribute-Based Access Control"]
        TenantIso["Tenant Isolation"]
        PolicyEng["Policy Engine<br/>(OPA/Rego)"]
    end

    subgraph AppSec["Application Security"]
        InputVal["Input Validation"]
        SQLiPrev["SQL Injection Prevention"]
        XSSPrev["XSS Prevention"]
        RateLimit["Rate Limiting"]
    end

    subgraph DataSec["Data Security"]
        Encryption["Encryption at Rest<br/>(AES-256)"]
        FieldEnc["Field-Level Encryption"]
        Tokenization["Sensitive Data Tokenization"]
        BackupEnc["Encrypted Backups"]
    end

    subgraph Monitoring["Security Monitoring"]
        SIEM["SIEM<br/>(Security Events)"]
        IDS["Intrusion Detection"]
        AuditLog["Audit Logging"]
        Anomaly["Anomaly Detection"]
    end

    Client["External Client"] --> DDoS
    DDoS --> WAF
    WAF --> IPFilter
    IPFilter --> GeoBlock
    GeoBlock --> TLS
    
    Service["Internal Service"] --> MTLS
    MTLS --> TLS
    
    TLS --> OAuth
    OAuth --> MFACheck
    MFACheck --> JWTVal
    JWTVal --> APIKey
    
    APIKey --> RBAC
    RBAC --> ABAC
    ABAC --> TenantIso
    TenantIso --> PolicyEng
    
    PolicyEng --> InputVal
    InputVal --> SQLiPrev
    SQLiPrev --> XSSPrev
    XSSPrev --> RateLimit
    
    RateLimit --> Encryption
    Encryption --> FieldEnc
    FieldEnc --> Tokenization
    Tokenization --> BackupEnc
    
    WAF -.->|"Alerts"| SIEM
    OAuth -.->|"Auth events"| AuditLog
    PolicyEng -.->|"Deny events"| SIEM
    RateLimit -.->|"Anomalies"| Anomaly
    Anomaly -.->|"Incidents"| IDS

    style Perimeter fill:#ffebee
    style Transport fill:#fff3e0
    style AuthN fill:#e3f2fd
    style AuthZ fill:#e8f5e9
    style AppSec fill:#fce4ec
    style DataSec fill:#f3e5f5
    style Monitoring fill:#fff9c4
```

### Security Layers

| Layer | Controls | Implementation |
|-------|----------|----------------|
| **Perimeter** | DDoS, WAF, Geo-blocking | Cloudflare, AWS Shield |
| **Network** | TLS, mTLS, VPC isolation | Envoy, Istio, AWS VPC |
| **Identity** | OAuth2, MFA, SSO | Auth0, AWS Cognito |
| **Access** | RBAC, ABAC, tenant isolation | Custom policy engine |
| **Application** | Input validation, rate limiting | FastAPI middleware |
| **Data** | Encryption, tokenization | AES-256-GCM, Vault |
| **Audit** | Logging, monitoring, SIEM | ELK, Prometheus |

### RBAC Model

```mermaid
flowchart LR
    subgraph Roles["Built-in Roles"]
        Owner["Owner<br/>Full access"]
        Admin["Admin<br/>Manage resources"]
        Developer["Developer<br/>Deploy & configure"]
        Viewer["Viewer<br/>Read-only"]
        Service["Service<br/>API-only access"]
    end

    subgraph Resources["Resources"]
        App["Applications"]
        Conv["Conversations"]
        Res["Resources"]
        Config["Configuration"]
        Billing["Billing"]
    end

    Owner -->|"CRUD + Delete tenant"| App
    Owner -->|"CRUD"| Conv
    Owner -->|"CRUD"| Res
    Owner -->|"CRUD"| Config
    Owner -->|"Read/Update"| Billing
    
    Admin -->|"CRUD"| App
    Admin -->|"CRUD"| Conv
    Admin -->|"CRUD"| Res
    Admin -->|"CRU"| Config
    
    Developer -->|"Read/Update"| App
    Developer -->|"Create"| Conv
    Developer -->|"Read"| Res
    Developer -->|"Read"| Config
    
    Viewer -->|"Read"| App
    Viewer -->|"Read"| Conv
    Viewer -->|"Read"| Res
    
    Service -->|"Limited API"| Conv

    style Roles fill:#e3f2fd
    style Resources fill:#e8f5e9
```

### Permission Matrix

| Resource | Owner | Admin | Developer | Viewer | Service |
|----------|-------|-------|-----------|--------|---------|
| Create Application | Yes | Yes | No | No | No |
| Delete Application | Yes | Yes | No | No | No |
| Update Config | Yes | Yes | Read-only | No | No |
| View Conversations | Yes | Yes | Yes | Yes | Yes |
| Delete Conversations | Yes | Yes | Own only | No | No |
| Upload Resources | Yes | Yes | Yes | No | No |
| Delete Resources | Yes | Yes | No | No | No |
| View Billing | Yes | No | No | No | No |
| API Access | Yes | Yes | Yes | Yes | Yes |

### Security Headers

| Header | Value | Purpose |
|--------|-------|---------|
| Strict-Transport-Security | max-age=31536000; includeSubDomains | Force HTTPS |
| Content-Security-Policy | default-src 'self' | XSS prevention |
| X-Frame-Options | DENY | Clickjacking prevention |
| X-Content-Type-Options | nosniff | MIME sniffing prevention |
| Referrer-Policy | strict-origin-when-cross-origin | Privacy |
| Permissions-Policy | geolocation=(), microphone=() | Feature restriction |

---

## Diagram Rendering

These diagrams use [Mermaid](https://mermaid-js.github.io/) syntax and can be rendered in:

- **GitHub/GitLab**: Native support in markdown files
- **VS Code**: Install Mermaid extension
- **Documentation**: Use mermaid-cli or mermaid.live
- **Confluence**: Use Mermaid macro

### Quick Render Checklist

- [ ] All diagrams display without syntax errors
- [ ] Node labels are readable
- [ ] Relationships clearly show direction
- [ ] Colors distinguish different layers/systems
- [ ] Text is not cut off or overlapping
