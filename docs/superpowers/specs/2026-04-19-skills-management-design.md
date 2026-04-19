# Skills 管理优化设计文档

**Created:** 2026-04-19
**Updated:** 2026-04-20
**Status:** Draft
**Reference:** https://github.com/qufei1993/skills-hub

---

## 1. Overview

### 1.1 目标

优化 SmartLink 前端 Skills 管理模块，参考 skills-hub 和 Nacos Skill Registry 设计模式，实现：
- Skills 列表页面（表格布局 + 领域筛选 + 搜索）
- Skill 详情页面（文件树 + Markdown 渲染 + 版本时间线）
- 后端 API（支持 SKILL.md 文件存储、打包下载）

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 渐进式披露 | 列表仅加载元数据，详情按需加载完整内容 |
| 标准格式 | 采用 SKILL.md 标准格式（YAML frontmatter + Markdown body） |
| 文件树浏览 | 支持多文件结构（SKILL.md + references + scripts） |
| Markdown 渲染 | 语法高亮 + 代码复制 + 表格支持 |
| 领域分类 | 资源领域、资产领域、运维领域、基础服务四类 |
| 主题一致性 | 使用 SmartLink 专业蓝主题配色 |

### 1.3 当前状态

| 功能 | 状态 | 差距 |
|------|------|------|
| SkillsManagement.vue | ✅ UI 完成 | 缺少领域筛选、表格布局 |
| SkillDetailPage.vue | ✅ UI 完成 | 缺少版本时间线、文件树 |
| Store skills.ts | ⚠️ Mock 数据 | 缺少后端 API 对接 |
| SkillFormDialog.vue | ⚠️ 功能不完整 | 缺少 Markdown 编辑器 |
| 后端 Skill API | ⚠️ 基础 CRUD | 缺少文件存储、打包下载 API |

---

## 2. 领域属性设计

### 2.1 领域分类

Skill 新增 `domain` 属性，用于业务领域分类：

```python
class SkillDomain(enum.Enum):
    RESOURCE = "resource"         # 资源领域：数据分析、数据处理
    ASSET = "asset"               # 资产领域：资产管理、追踪监控
    OPERATION = "operation"       # 运维领域：系统监控、运维管理
    INFRASTRUCTURE = "infrastructure"  # 基础服务：API接口、基础工具
```

### 2.2 领域标签样式（SmartLink 主题）

| 领域 | 图标 | 背景色 | 文字色 |
|------|------|--------|--------|
| 📦 资源领域 | resource | `rgba(59, 130, 246, 0.08)` | `#3b82f6` (主色) |
| 💎 资产领域 | asset | `rgba(217, 119, 6, 0.08)` | `#d97706` (警告色) |
| 🛠️ 运维领域 | operation | `rgba(5, 150, 105, 0.08)` | `#059669` (成功色) |
| ⚡ 基础服务 | infrastructure | `rgba(139, 92, 246, 0.08)` | `#8b5cf6` (紫色) |

### 2.3 前端类型定义

```typescript
export type SkillDomain = 'resource' | 'asset' | 'operation' | 'infrastructure'

const DOMAIN_CONFIG: Record<SkillDomain, { icon: string; color: string; bgColor: string }> = {
  resource: { icon: '📦', color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.08)' },
  asset: { icon: '💎', color: '#d97706', bgColor: 'rgba(217, 119, 6, 0.08)' },
  operation: { icon: '🛠️', color: '#059669', bgColor: 'rgba(5, 150, 105, 0.08)' },
  infrastructure: { icon: '⚡', color: '#8b5cf6', bgColor: 'rgba(139, 92, 246, 0.08)' }
}
```

---

## 3. Skills 列表页设计（表格布局）

### 3.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  顶部导航: SmartLink | AI 智能平台                                │
│  [MCP Server] [Agent] [Skill 管理✓] [Prompt]           👤 admin  │
├──────────────────────────────────────────────────────────────────┤
│  左侧菜单 (220px):                                                │
│  ┌─────────────┐                                                 │
│  │ AI 注册中心 │                                                 │
│  │ 📦 MCP Server│                                                │
│  │ 🤖 Agent     │                                                │
│  │ ⚡ Skill 管理 ✓│                                               │
│  │ 📝 Prompt    │                                                 │
│  ├─────────────┤                                                 │
│  │ 平台管理    │                                                 │
│  │ 📁 命名空间 │                                                 │
│  │ 👥 权限控制 │                                                 │
│  └─────────────┘                                                 │
├──────────────────────────────────────────────────────────────────┤
│  主内容区:                                                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Skill 管理                    [搜索框] [上传ZIP] [+创建]    │ │
│  ├─────────────────────────────────────────────────────────────┤ │
│  │ 统计卡片:  📦 15 总数  ✅ 12 已上线  📝 3 草稿             │ │
│  ├─────────────────────────────────────────────────────────────┤ │
│  │ 表格:                                                        │ │
│  │ | 名称       | 领域       | 描述     | 版本数 | 下载量 | 状态 | │
│  │ |------------|------------|----------|--------|--------|------| │
│  │ | data-analyzer | 📦资源领域 | 智能分析... | 3 | 1,542 | ONLINE | │
│  │ | asset-tracker | 💎资产领域 | 资产追踪... | 2 | 823 | ONLINE | │
│  │ | ops-monitor | 🛠️运维领域 | 运维监控... | 4 | 2,156 | ONLINE | │
│  │ | base-service | ⚡基础服务 | 基础API... | 1 | 4,562 | ONLINE | │
│  │ | report-gen | 📦资源领域 | 报告生成... | 0 | 0 | DRAFT | │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 表格字段

| 列名 | 数据来源 | 说明 |
|------|----------|------|
| 名称 | `name` | Skill 标识符 |
| 领域 | `domain` | 领域标签（带颜色） |
| 描述 | `description` | 截断 50 字符 |
| 版本数 | `version_count` | 在线版本数量 |
| 下载量 | `stats.downloads` | 累计下载次数 |
| 状态 | `status` | ONLINE/DRAFT/OFFLINE 标签 |
| 更新时间 | `updated_at` | 格式化日期 |
| 操作 | - | 详情按钮 |

---

## 4. Skill 详情页设计

### 4.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  详情头部:                                                        │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ data-analyzer  [📦 资源领域] [ONLINE✓]                      │ │
│  │ 智能数据分析技能，支持多维度数据统计、可视化和洞察生成...      │ │
│  │ 👤 作者: SmartLink Team  📋 MIT  📅 2026-03-01  🔄 2026-04-18 │ │
│  │                                [📤 导出ZIP] [📋 复制] [✏️ 编辑]│ │
│  └─────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│  详情主体 (左侧内容 + 右侧信息卡片):                               │
│  ┌───────────────────────────────────┬─────────────────────────┐ │
│  │ 内容编辑区 (flex: 1)              │ 信息侧边栏 (300px)      │ │
│  │ ┌───────────────────────────────┐ │ ┌─────────────────────┐ │ │
│  │ │ Tab: [SKILL.md✓] [文件树] [Schema] [配置] [统计] │ │ │ │ 基本信息         │ │ │
│  │ ├───────────────────────────────┤ │ │ 领域: 📦 资源领域   │ │ │
│  │ │ Markdown 内容:                │ │ │ 风险: 🟢 低风险     │ │ │
│  │ │ # data-analyzer               │ │ │ 可见性: PUBLIC      │ │ │
│  │ │                               │ │ │ 下载量: 1,542       │ │ │
│  │ │ ## Overview                   │ │ │ 在线版本: 3         │ │ │
│  │ │ 智能数据分析技能...            │ │ └─────────────────────┘ │ │
│  │ │                               │ │ ┌─────────────────────┐ │ │
│  │ │ ## Input Schema               │ │ │ 版本时间线          │ │ │
│  │ │ | Property | Type | Required | │ │ ┌─────────────────┐ │ │ │
│  │ │                               │ │ │ │ v2.1.0 ONLINE✓  │ │ │ │
│  │ │ ## Examples                   │ │ │ │ 2026-04-18      │ │ │ │
│  │ │ ```json                       │ │ │ └─────────────────┘ │ │ │
│  │ │ { ... }                       │ │ │ ┌─────────────────┐ │ │ │
│  │ │ ```                           │ │ │ │ v2.0.0 OFFLINE │ │ │ │
│  │ └───────────────────────────────┘ │ │ └─────────────────┘ │ │
│  │                                   │ └─────────────────────┘ │ │
│  │                                   │ ┌─────────────────────┐ │ │
│  │                                   │ │ CLI 安装命令        │ │ │
│  │                                   │ │ nacos-cli skill-get │ │ │
│  │                                   │ │ [📋 复制]           │ │ │
│  │                                   │ └─────────────────────┘ │ │
│  │                                   │ ┌─────────────────────┐ │ │
│  │                                   │ │ 打包下载            │ │ │
│  │                                   │ │ [📦 导出为 ZIP]     │ │ │
│  │                                   │ └─────────────────────┘ │ │
│  └───────────────────────────────────┴─────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 功能要点

| 功能 | 说明 |
|------|------|
| 版本时间线 | 右侧卡片展示所有版本，点击切换预览 |
| CLI 命令卡片 | 提供安装命令，一键复制 |
| 打包下载 | 导出 Skill 所有文件为 ZIP |
| Tab 切换 | SKILL.md / 文件树 / Schema / 配置 / 统计 |

---

## 5. 打包下载 API 设计

### 5.1 API 端点

```
GET /api/v1/skills/{id}/export
```

### 5.2 响应

```python
# 返回 ZIP 文件流
@router.get("/skills/{skill_id}/export")
async def export_skill(skill_id: str):
    """
    打包下载 Skill 所有文件
    
    返回包含:
    - SKILL.md
    - README.md
    - references/*.md
    - examples/*.json
    - scripts/*.py
    """
    skill = await skill_service.get_skill(skill_id)
    files = await skill_service.get_skill_files(skill_id)
    
    # 生成 ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.writestr(file.path, file.content)
    
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={skill.name}.zip"
        }
    )
```

### 5.3 ZIP 文件结构

```
skill-name.zip
├── SKILL.md              # 主文件
├── README.md             # 说明文档
├── references/           # 参考文档
│   ├── api-guide.md
│   └── best-practices.md
├── examples/             # 示例用例
│   └── demo.json
└── scripts/              # 可执行脚本
    └── helper.py
```

---

## 6. SmartLink 专业蓝主题配色

### 6.1 主题变量（来自 `variables.scss`）

| 类别 | CSS 变量 | 颜色值 | 用途 |
|------|----------|--------|------|
| 主色 | `--primary-color` | `#3b82f6` | 按钮、链接、选中态 |
| 主色浅 | `--primary-light` | `#60a5fa` | 悬浮状态 |
| 主色深 | `--primary-dark` | `#2563eb` | 按下状态 |
| 辅助色 | `--secondary-color` | `#059669` | 成功状态、辅助操作 |
| 强调色 | `--accent-color` | `#22c55e` | CTA 按钮 |
| 背景主色 | `--bg-primary` | `#ffffff` | 卡片、表格背景 |
| 背景次色 | `--bg-secondary` | `#f8fafc` | 页面背景 |
| 背景三级 | `--bg-tertiary` | `#f1f5f9` | 次要背景 |
| 边框色 | `--border-color-base` | `#e2e8f0` | 分割线、边框 |
| 文字主色 | `--text-primary` | `#0f172a` | 标题、重要文字 |
| 文字次色 | `--text-secondary` | `#475569` | 正文、描述 |
| 文字三级 | `--text-tertiary` | `#94a3b8` | 次要、提示文字 |
| 成功色 | `--success` | `#059669` | ONLINE 状态 |
| 警告色 | `--warning` | `#d97706` | DRAFT 状态 |
| 错误色 | `--error` | `#dc2626` | OFFLINE/Error |

### 6.2 渐变和阴影

```scss
// 渐变
--gradient-primary: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);

// 阴影
--shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
--shadow-card: 0 1px 3px rgba(15, 23, 42, 0.04);
--shadow-card-hover: 0 8px 24px rgba(15, 23, 42, 0.08);
--shadow-primary: 0 4px 14px rgba(59, 130, 246, 0.2);
```

### 6.3 圆角系统

```scss
$border-radius-sm: 4px;
$border-radius-md: 8px;
$border-radius-lg: 12px;
```

---

## 7. 数据模型更新

### 7.1 Skill 模型（更新）

```python
class Skill(Base):
    __tablename__ = "skills"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 分类
    category: Mapped[SkillCategory] = mapped_column(default=SkillCategory.CUSTOM)
    domain: Mapped[SkillDomain] = mapped_column(default=SkillDomain.RESOURCE)  # 新增
    status: Mapped[SkillStatus] = mapped_column(default=SkillStatus.ENABLED)
    
    # 版本与作者
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    author: Mapped[str] = mapped_column(String(128))
    maintainer: Mapped[Optional[str]] = mapped_column(String(128))
    license: Mapped[Optional[str]] = mapped_column(String(64))
    
    # 元数据
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    icon: Mapped[Optional[str]] = mapped_column(String(256))
    
    # 风险控制
    risk_level: Mapped[SkillRiskLevel] = mapped_column(default=SkillRiskLevel.LOW)
    requires_approval: Mapped[bool] = mapped_column(default=False)
    
    # 可见性
    visibility: Mapped[SkillVisibility] = mapped_column(default=SkillVisibility.PUBLIC)  # 新增
    
    # Schema
    input_schema: Mapped[Dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[Dict] = mapped_column(JSON, default=dict)
    
    # 配置
    config: Mapped[Dict] = mapped_column(JSON, default=dict)
    dependencies: Mapped[Dict] = mapped_column(JSON, default=dict)
    stats: Mapped[Dict] = mapped_column(JSON, default=dict)
    
    # 来源
    source_type: Mapped[Optional[str]] = mapped_column(String(32))
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    
    # 租户
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    
    # 时间
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column()
    
    # 关系
    files: Mapped[List[SkillFile]] = relationship(back_populates="skill", cascade="all, delete")
    versions: Mapped[List[SkillVersion]] = relationship(back_populates="skill", cascade="all, delete")  # 新增
```

### 7.2 SkillVersion 模型（新增）

```python
class SkillVersion(Base):
    """Skill 版本表 - 支持版本时间线"""
    __tablename__ = "skill_versions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    
    # 版本信息
    version: Mapped[str] = mapped_column(String(32))  # e.g., "2.1.0"
    status: Mapped[SkillVersionStatus] = mapped_column()  # DRAFT/REVIEWING/ONLINE/OFFLINE
    
    # 标签
    labels: Mapped[List[str]] = mapped_column(JSON, default=list)  # latest/stable/canary
    
    # 时间
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    published_at: Mapped[Optional[datetime]] = mapped_column()
    
    # 关系
    skill: Mapped[Skill] = relationship(back_populates="versions")
```

---

## 8. 前端类型定义更新

```typescript
export type SkillDomain = 'resource' | 'asset' | 'operation' | 'infrastructure'
export type SkillVisibility = 'public' | 'private'
export type SkillVersionStatus = 'draft' | 'reviewing' | 'online' | 'offline'

export interface SkillListItem {
  id: string
  name: string
  displayName: string
  description: string
  domain: SkillDomain          // 新增
  category: SkillCategory
  status: SkillStatus
  versionCount: number         // 新增
  downloads: number            // 新增
  updatedAt: number
}

export interface SkillDetail extends SkillListItem {
  visibility: SkillVisibility  // 新增
  versions: SkillVersion[]     // 新增
  files: SkillFileNode[]
  stats: SkillStats
  config: SkillConfig
  dependencies: SkillDependencies
}

export interface SkillVersion {
  id: string
  version: string
  status: SkillVersionStatus
  labels: string[]
  createdAt: number
  publishedAt?: number
}
```

---

## 9. 实施计划更新

### Phase 1: 后端 API (P0)

| 任务 | 工作量 | 依赖 |
|------|--------|------|
| 更新 Skill/SkillVersion 数据模型 | 3h | 无 |
| 实现 Skills 列表 API（含领域筛选） | 3h | 数据模型 |
| 实现文件存储 API | 3h | 数据模型 |
| 实现打包下载 API | 2h | 文件存储 |
| 实现版本时间线 API | 2h | SkillVersion模型 |
| 数据库迁移脚本 | 1h | 数据模型 |

### Phase 2: 前端对接 (P0)

| 任务 | 工作量 | 依赖 |
|------|--------|------|
| 更新 skills store（真实 API） | 2h | Phase 1 |
| 创建 SkillFileTree 组件 | 3h | 无 |
| 创建 MarkdownRenderer 组件 | 2h | 无 |
| 创建 VersionTimeline 组件 | 2h | 无 |
| 更新 SkillsManagement.vue（表格布局） | 3h | store |
| 更新 SkillDetailPage.vue | 4h | 组件 |
| 添加打包下载功能 | 1h | Phase 1 |

### Phase 3: 增强 (P1)

| 任务 | 工作量 | 依赖 |
|------|--------|------|
| 完善 SkillFormDialog | 3h | Phase 2 |
| 实现高级搜索 | 4h | Phase 2 |
| 实现导入/导出功能 | 3h | Phase 2 |

### 总工作量

- **Phase 1:** 14h
- **Phase 2:** 14h  
- **Phase 3:** 10h
- **总计:** 38h (~5 人天)

---

## 10. 附录

### 10.1 领域图标和颜色

```typescript
const DOMAIN_CONFIG: Record<SkillDomain, { icon: string; color: string; bgColor: string }> = {
  resource: { 
    icon: '📦', 
    color: '#3b82f6', 
    bgColor: 'rgba(59, 130, 246, 0.08)' 
  },
  asset: { 
    icon: '💎', 
    color: '#d97706', 
    bgColor: 'rgba(217, 119, 6, 0.08)' 
  },
  operation: { 
    icon: '🛠️', 
    color: '#059669', 
    bgColor: 'rgba(5, 150, 105, 0.08)' 
  },
  infrastructure: { 
    icon: '⚡', 
    color: '#8b5cf6', 
    bgColor: 'rgba(139, 92, 246, 0.08)' 
  }
}
```

### 10.2 状态颜色映射（SmartLink 主题）

```typescript
const STATUS_COLORS: Record<SkillStatus, { color: string; bgColor: string }> = {
  enabled: { 
    color: '#059669',     // --success
    bgColor: 'rgba(5, 150, 105, 0.08)'
  },
  disabled: { 
    color: '#dc2626',     // --error
    bgColor: 'rgba(220, 38, 38, 0.08)'
  },
  deprecated: { 
    color: '#d97706',     // --warning
    bgColor: 'rgba(217, 119, 6, 0.08)'
  }
}

const VERSION_STATUS_COLORS: Record<SkillVersionStatus, { color: string; bgColor: string }> = {
  draft: { color: '#d97706', bgColor: 'rgba(217, 119, 6, 0.08)' },
  reviewing: { color: '#0284c7', bgColor: 'rgba(2, 132, 199, 0.08)' },
  online: { color: '#059669', bgColor: 'rgba(5, 150, 105, 0.08)' },
  offline: { color: '#94a3b8', bgColor: 'rgba(148, 163, 184, 0.08)' }
}
```

### 10.3 文件 MIME 类型映射

```typescript
const MIME_TYPES: Record<string, string> = {
  '.md': 'text/markdown',
  '.py': 'text/x-python',
  '.js': 'text/javascript',
  '.ts': 'text/typescript',
  '.json': 'application/json',
  '.sh': 'text/x-shellscript',
  '.yaml': 'text/yaml',
  '.txt': 'text/plain'
}
```

### 10.4 UX Mockup 文件

完整 UX 设计 mockup 已保存至：
- `.superpowers/ux-mockup/skills-ux-nacos-style.html`
|------|------|
| 点击卡片 | 跳转详情页 `/app/skill/{id}` |
| 测试按钮 | 弹出 SkillTestDialog |
| 编辑按钮 | 弹出 SkillFormDialog (编辑模式) |
| 新建按钮 | 弹出 SkillFormDialog (新建模式) |
| 导入按钮 | 弹出 SkillImportDialog |

---

## 3. Skill 详情页设计

### 3.1 页面布局（左右分栏）

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回列表    {displayName}            [编辑] [测试]   │
├───────────────────┬─────────────────────────────────────┤
│  文件树            │  内容预览                           │
│  (240px 固定宽度)   │                                     │
│                   │                                     │
│  📁 {skill-name}  │  ┌─────────────────────────────────┐│
│  ├─ 📄 SKILL.md ● │  │ ## Overview                     ││
│  ├─ 📄 README.md  │  │                                 ││
│  ├─ 📁 references │  │ {markdown content rendered}     ││
│  │  ├─ 📄 api.md  │  │                                 ││
│  │  └─ 📄 guide.md│  │ ## Input Schema                 ││
│  ├─ 📁 examples   │  │ | Property | Type | Required | ││
│  │  └─ 📄 demo.json│ │ {table content}                 ││
│  └─ 📁 scripts    │  │                                 ││
│     └─ 📄 helper.py│ │ ## Code Example                 ││
│                   │  │ ```python                       ││
│  ──────────────── │  │ {code with syntax highlight}    ││
│                   │  │ ```                             ││
│  元数据面板:       │  └─────────────────────────────────┘│
│  版本: v{version}  │                                     │
│  作者: {author}    │                                     │
│  许可证: {license} │                                     │
│  分类: {category}  │                                     │
│  标签: [tag list]  │                                     │
│  风险: {riskLevel} │                                     │
│                   │                                     │
│  依赖:             │                                     │
│  - {dep1}         │                                     │
│  - {dep2}         │                                     │
│                   │                                     │
│  [复制配置]       │                                     │
└───────────────────┴─────────────────────────────────────┘
```

### 3.2 文件树组件

**功能：**
- 折叠/展开目录
- 点击文件 → 右侧显示内容
- 当前选中文件高亮
- 文件类型图标区分

**文件类型图标映射：**
```typescript
const FILE_ICONS: Record<string, string> = {
  '.md': '📄',    // Markdown
  '.py': '🐍',    // Python
  '.js': '📜',    // JavaScript
  '.ts': '📜',    // TypeScript
  '.json': '📋',  // JSON
  '.sh': '⚡',    // Shell
  '.yaml': '⚙️', // YAML
  '.txt': '📄',   // Text
  'default': '📄'
}

function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop() || ''
  return FILE_ICONS['.' + ext] || FILE_ICONS.default
}
```

### 3.3 Markdown 渲染器

**技术选型：** `markdown-it` + `highlight.js`

**功能：**
- 语法高亮（40+ 语言）
- 代码块复制按钮
- 表格渲染
- YAML frontmatter 解析展示
- TOC 目录导航（可选）

**实现示例：**
```typescript
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const mdRenderer = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: (str: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch {}
    }
    return ''
  }
})

// 前置 YAML frontmatter 解析
function parseFrontmatter(content: string): { meta: object; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  if (match) {
    const yamlContent = match[1]
    const body = match[2]
    // 解析 YAML 到对象
    const meta = parseYaml(yamlContent)
    return { meta, body }
  }
  return { meta: {}, body: content }
}
```

### 3.4 元数据面板

| 字段 | 数据来源 | 展示方式 |
|------|----------|---------|
| 版本 | `version` | `v{version}` |
| 作者 | `author` | 文本 |
| 维护者 | `maintainer` | 文本（可选） |
| 许可证 | `license` | SPDX 标识 |
| 分类 | `category` | 图标 + 文本 |
| 标签 | `tags` | 标签列表 |
| 风险等级 | `riskLevel` | 颜色点 + 文字 |
| 需审批 | `requiresApproval` | 是/否 |
| 依赖 | `dependencies` | 列表形式 |

---

## 4. 后端 API 设计

### 4.1 API 端点清单

| 端点 | 方法 | 功能 | 响应 |
|------|------|------|------|
| `/api/v1/skills` | GET | Skills 列表 | 列表 + 分页 |
| `/api/v1/skills` | POST | 创建 Skill | Skill 对象 |
| `/api/v1/skills/{id}` | GET | Skill 详情 | Skill + 文件树 |
| `/api/v1/skills/{id}` | PUT | 更新 Skill | Skill 对象 |
| `/api/v1/skills/{id}` | DELETE | 删除 Skill | 204 |
| `/api/v1/skills/{id}/files` | GET | 文件树 | 文件树结构 |
| `/api/v1/skills/{id}/files/{path}` | GET | 文件内容 | 文件内容 |
| `/api/v1/skills/{id}/files/{path}` | PUT | 更新文件 | 204 |
| `/api/v1/skills/{id}/test` | POST | 测试 Skill | 测试结果 |
| `/api/v1/skills/{id}/activate` | POST | 激活 Skill | 204 |
| `/api/v1/skills/{id}/deactivate` | POST | 停用 Skill | 204 |
| `/api/v1/skills/import` | POST | 导入 Skill | Skill 对象 |
| `/api/v1/skills/{id}/export` | GET | 导出配置 | JSON 文件 |

### 4.2 Schema 定义

**列表响应（轻量）：**
```python
class SkillListItem(BaseModel):
    id: str
    name: str
    display_name: str
    description: str          # 截断版本 (80字符)
    version: str
    category: SkillCategory
    status: SkillStatus
    tags: List[str]
    icon: Optional[str]
    risk_level: SkillRiskLevel
    stats: SkillStatsSummary
    created_at: datetime
    updated_at: datetime

class SkillListResponse(BaseModel):
    skills: List[SkillListItem]
    pagination: PaginationInfo
```

**详情响应（完整）：**
```python
class SkillDetail(BaseModel):
    id: str
    name: str
    display_name: str
    description: str          # 完整版本
    version: str
    category: SkillCategory
    status: SkillStatus
    tags: List[str]
    icon: Optional[str]
    risk_level: SkillRiskLevel
    requires_approval: bool
    author: str
    maintainer: Optional[str]
    license: Optional[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    config: SkillConfig
    dependencies: SkillDependencies
    stats: SkillStats
    files: SkillFileTree
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime]
```

**文件内容响应：**
```python
class SkillFileContent(BaseModel):
    path: str
    content: str              # 文件原始内容
    mime_type: str
    size: int
    encoding: str = "utf-8"
    last_modified: datetime
```

**创建/更新请求：**
```python
class SkillCreate(BaseModel):
    name: str                 # kebab-case, 唯一
    display_name: str
    description: str
    category: SkillCategory
    tags: List[str] = []
    skill_md_content: str     # SKILL.md 内容
    files: Optional[List[SkillFileUpload]] = None
    config: Optional[SkillConfig] = None

class SkillFileUpload(BaseModel):
    path: str                 # 相对路径
    content: str

class SkillUpdate(BaseModel):
    display_name: Optional[str]
    description: Optional[str]
    category: Optional[SkillCategory]
    tags: Optional[List[str]]
    status: Optional[SkillStatus]
    config: Optional[SkillConfig]
```

---

## 5. 数据模型设计

### 5.1 后端数据库模型

**Skill 主表：**
```python
class Skill(Base):
    __tablename__ = "skills"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[SkillCategory] = mapped_column(default=SkillCategory.CUSTOM)
    status: Mapped[SkillStatus] = mapped_column(default=SkillStatus.ENABLED)
    
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    author: Mapped[str] = mapped_column(String(128))
    maintainer: Mapped[Optional[str]] = mapped_column(String(128))
    license: Mapped[Optional[str]] = mapped_column(String(64))
    
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    icon: Mapped[Optional[str]] = mapped_column(String(256))
    
    risk_level: Mapped[SkillRiskLevel] = mapped_column(default=SkillRiskLevel.LOW)
    requires_approval: Mapped[bool] = mapped_column(default=False)
    
    input_schema: Mapped[Dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[Dict] = mapped_column(JSON, default=dict)
    config: Mapped[Dict] = mapped_column(JSON, default=dict)
    dependencies: Mapped[Dict] = mapped_column(JSON, default=dict)
    stats: Mapped[Dict] = mapped_column(JSON, default=dict)
    
    source_type: Mapped[Optional[str]] = mapped_column(String(32))
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    last_used_at: Mapped[Optional[datetime]] = mapped_column()
    
    tenant: Mapped[Tenant] = relationship()
    files: Mapped[List[SkillFile]] = relationship(back_populates="skill", cascade="all, delete")
```

**SkillFile 文件表：**
```python
class SkillFile(Base):
    __tablename__ = "skill_files"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="text/markdown")
    encoding: Mapped[str] = mapped_column(String(16), default="utf-8")
    size: Mapped[int] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    
    skill: Mapped[Skill] = relationship(back_populates="files")
    
    __table_args__ = (
        UniqueConstraint("skill_id", "path", name="uq_skill_file_path"),
    )
```

### 5.2 前端 TypeScript 类型

```typescript
export type SkillCategory = 'builtin' | 'custom' | 'online'
export type SkillStatus = 'enabled' | 'disabled' | 'deprecated'
export type SkillRiskLevel = 'low' | 'medium' | 'high'

export interface SkillListItem {
  id: string
  name: string
  displayName: string
  description: string
  version: string
  category: SkillCategory
  status: SkillStatus
  tags: string[]
  icon?: string
  riskLevel: SkillRiskLevel
  stats: { totalCalls: number; successRate: number; avgDuration: number }
  createdAt: number
  updatedAt: number
}

export interface SkillDetail extends SkillListItem {
  description: string
  author: string
  maintainer?: string
  license?: string
  requiresApproval: boolean
  inputSchema: Record<string, any>
  outputSchema: Record<string, any>
  config: SkillConfig
  dependencies: SkillDependencies
  stats: SkillStats
  files: SkillFileNode[]
  lastUsedAt?: number
}

export interface SkillFileNode {
  name: string
  type: 'file' | 'directory'
  path: string
  children?: SkillFileNode[]
  size?: number
  mimeType?: string
}

export interface SkillFileContent {
  path: string
  content: string
  mimeType: string
  size: number
  encoding: string
  lastModified: number
}
```

---

## 6. SKILL.md 标准格式

### 6.1 文件结构

```
skill-name/
├── SKILL.md              # 必需：技能定义
├── README.md             # 可选：人类文档
├── references/           # 可选：参考文档
│   └── guide.md
├── examples/             # 可选：示例用例
│   └── demo.json
├── scripts/              # 可选：可执行脚本
│   └── helper.py
└── LICENSE.txt           # 可选：许可证
```

### 6.2 SKILL.md 格式规范

```yaml
---
# === 必需字段 ===
name: skill-name                          # kebab-case, 1-64 字符
description: >                            # 1-1024 字符
  Brief description of:
  1) What this skill does
  2) When it should be used

# === 可选字段 ===
version: 1.0.0                            # 语义化版本
author: Author Name <email@example.com>  # 作者信息
license: MIT                              # SPDX 许可证
tags: [tag1, tag2, tag3]                  # 分类标签
icon: 📊                                  # Emoji 或 URL
category: builtin | custom | online       # 分类
riskLevel: low | medium | high            # 风险等级
requiresApproval: false                   # 是否需要审批

# === Schema 定义 ===
inputSchema:
  type: object
  properties:
    param1: { type: string, description: "..." }
outputSchema:
  type: object
  properties:
    result: { type: string }

# === 配置 ===
config:
  model: gpt-4o
  temperature: 0.3
  maxTokens: 4096
  toolBindings: [tool1, tool2]
  guardrails:
    validateInput: true
    privacyCheck: true
    maxRetries: 3
  resources:
    timeout: 120
    maxMemory: 1024
    maxConcurrency: 5

# === 依赖 ===
dependencies:
  skills: [{ id: skill-001, version: 1.0.0 }]
  tools: [database-query, http-client]
  mcpServers: [api-gateway]
---

# Markdown Body (系统提示词)

## Overview
技能概述、使用场景、技术背景

## Prerequisites
运行环境、依赖、所需权限

## Workflow
分步骤指导：输入、处理、输出

## Input Schema
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| param1   | string | Yes | ... |

## Output Schema
输出格式说明

## Examples
典型案例（代码示例、输入输出格式）

## Best Practices
经验性提示、注意事项

## Troubleshooting
常见问题和解决方案
```

---

## 7. 实施计划

### 7.1 Phase 1: 后端 API (P0)

| 任务 | 工作量 | 依赖 |
|------|--------|------|
| 创建 Skill/SkillFile 数据模型 | 2h | 无 |
| 实现 Skills CRUD API | 4h | 数据模型 |
| 实现文件存储 API | 3h | 数据模型 |
| 实现 Skill 测试 API | 2h | CRUD API |
| 数据库迁移脚本 | 1h | 数据模型 |
| API 测试 | 2h | 全部 |

### 7.2 Phase 2: 前端对接 (P0)

| 任务 | 工作量 | 依赖 |
|------|--------|------|
| 更新 skills store (对接真实 API) | 2h | Phase 1 |
| 创建 SkillFileTree 组件 | 3h | 无 |
| 创建 MarkdownRenderer 组件 | 2h | 无 |
| 更新 SkillsManagement.vue | 2h | store |
| 更新 SkillDetailPage.vue | 4h | FileTree, Renderer |
| 创建 SkillImportDialog | 2h | store |

### 7.3 Phase 3: 增强 (P1)

| 任务 | 工作量 | 依赖 |
|------|--------|------|
| 完善 SkillFormDialog (Markdown 编辑) | 3h | Phase 2 |
| 实现高级搜索 (语义搜索) | 4h | Phase 2 |
| 实现批量操作 | 2h | Phase 2 |
| 实现导入/导出功能 | 3h | Phase 2 |

### 7.4 总工作量估算

- **Phase 1 (后端):** 14h
- **Phase 2 (前端):** 13h
- **Phase 3 (增强):** 12h
- **总计:** 39h (~5 人天)

---

## 8. 技术选型

### 8.1 前端

| 类别 | 选型 | 理由 |
|------|------|------|
| Markdown 渲染 | `markdown-it` + `highlight.js` | 轻量 + 语法高亮 |
| 文件树 | 自实现 (Vue 组件) | 简单需求，无需复杂库 |
| 状态管理 | Pinia (现有) | 项目已使用 |
| UI 组件 | Element Plus (现有) | 项目已使用 |

### 8.2 后端

| 类别 | 选型 | 理由 |
|------|------|------|
| 数据库 | SQLite (现有) | 项目已使用 |
| ORM | SQLAlchemy (现有) | 项目已使用 |
| API | FastAPI (现有) | 项目已使用 |
| YAML 解析 | `pyyaml` | 解析 frontmatter |

---

## 9. 参考资料对比

| 特性 | skills-hub | SmartLink (设计后) |
|------|------------|-------------------|
| 统一视图 | ✅ | ✅ 列表页 + 详情页 |
| 文件树浏览 | ✅ | ✅ 左侧文件树 |
| Markdown 渲染 | ✅ | ✅ 右侧内容预览 |
| 代码高亮 | ✅ Shiki | ✅ highlight.js |
| 多工具同步 | ✅ symlink/copy | ❌ (单系统) |
| Git 导入 | ✅ | ✅ import API |
| Scope 控制 | ✅ Global/Project | ❌ (暂无) |
| 使用统计 | ❌ | ✅ stats 字段 |

---

## 10. 附录

### 10.1 默认分类图标

```typescript
const CATEGORY_ICONS: Record<SkillCategory, string> = {
  builtin: '📦',
  custom: '🔧',
  online: '🌐'
}
```

### 10.2 状态颜色映射

```typescript
const STATUS_COLORS: Record<SkillStatus, string> = {
  enabled: '#52c41a',    // 绿色
  disabled: '#f5222d',   // 红色
  deprecated: '#faad14'  // 黄色
}

const RISK_COLORS: Record<SkillRiskLevel, string> = {
  low: '#52c41a',
  medium: '#faad14',
  high: '#f5222d'
}
```

### 10.3 文件 MIME 类型映射

```typescript
const MIME_TYPES: Record<string, string> = {
  '.md': 'text/markdown',
  '.py': 'text/x-python',
  '.js': 'text/javascript',
  '.ts': 'text/typescript',
  '.json': 'application/json',
  '.sh': 'text/x-shellscript',
  '.yaml': 'text/yaml',
  '.txt': 'text/plain'
}
```