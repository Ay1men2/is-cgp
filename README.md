---

```markdown
# IS-CGP — 智安对话治理平台

**Intelligent Secure Conversation Governance Platform**

---

## 项目定位（Positioning）

**IS-CGP（智安对话治理平台）** 是一个面向 **内网 / 私有化部署场景** 的  
**大模型会话治理中间层（Governance Middleware, Open Core）**。

IS-CGP 不追求替代模型、不绑定聊天 UI，也不提供推理能力本身。  
其核心目标是解决一个在真实组织中不可回避的问题：

> **当大模型被多项目、多部门、多角色长期使用时，  
> “哪些信息可以进入模型上下文、为什么进入”，  
> 必须是可治理、可解释、可审计的。**

当前阶段，IS-CGP 聚焦于一个明确、可验证的工程目标：

> **围绕工程化 RLM（Retrieval / Logic / Memory），  
> 构建一个受控、确定、可回放的上下文治理执行单元，  
> 并在长上下文场景下验证其工程稳定性与治理边界。**

> **EN**  
> IS-CGP is an open-core governance middleware that focuses on **auditable and controllable context assembly** for LLMs in on-premise environments.

---

## 一、背景与动机（Why）

随着大模型在 **政务、医疗、科研机构等内网环境** 中逐步落地，其使用形态正从“个人试验”转向：

> **多项目 / 多部门 / 多角色的长期共享基础设施**

在这一阶段，系统瓶颈不再主要体现在模型推理性能或算力利用率，而是集中暴露在 **治理层面**：

- 多项目并行使用下，**上下文与数据隔离不足**
- 内部制度文件、科研资料、源代码等资产  
  **难以按角色与保密等级进行精细控制**
- 模型输出缺乏清晰的 **可审计、可解释路径**
- 检索与缓存机制在策略或权限变化后  
  **缺乏统一、可靠的失效与回溯机制**
- 在 **长上下文（Long Context）** 场景下：
  - 给多少上下文
  - 给哪些上下文
  - 出现问题如何追责  
  往往缺乏系统化答案

现有方案多聚焦于模型能力或应用层体验，  
而 **缺乏一个独立、工程化的治理中间层**。

IS-CGP 正是在这一背景下提出，用于补齐  
**内网大模型基础设施中的治理能力短板**。

---

## 二、IS-CGP 是什么（What）

IS-CGP 定位为 **大模型服务的治理中间层**，部署在：

```

现有聊天 UI / 业务系统
↓
IS-CGP
↓
模型推理后端
(llama.cpp / vLLM / others)

```

它 **不替代 UI、不侵入模型、不干预推理实现**，  
而是为所有模型调用提供统一、可审计的治理能力。

---

### 核心能力（Capability-Oriented）

- **会话与项目级隔离**
  - Session / Project 作为最小治理单元
  - 防止跨项目、跨任务的上下文污染

- **上下文治理流水线（RLM-style）**
  - 采用工程化 RLM（Retrieval / Logic / Memory）语义
  - 在推理前，对上下文进行：
    - 检索
    - 过滤
    - 排序
    - 截断
  - 决策过程确定、可解释、可回放

- **长上下文治理**
  - 在大上下文长度场景下：
    - 控制上下文规模
    - 明确上下文来源
    - 约束缓存与复用行为

- **审计与证据链（Audit & Trace）**
  - 记录每一次上下文治理决策
  - 支持事后审计、问题回放与责任界定

---

## 三、IS-CGP 不是什么（What IS-CGP Is NOT）

为避免误解，IS-CGP **明确不承担** 以下职责：

- ❌ 模型训练、微调或推理优化框架
- ❌ Agent / Planner / AutoGPT 系统
- ❌ 聊天 UI 或前端产品
- ❌ 公网 SaaS 或多租户托管服务
- ❌ 无边界共享 KV Cache 的性能优先系统

IS-CGP 优先保证 **治理正确性、可解释性与审计可靠性**，  
而非激进的性能复用或智能叠加。

---

## 四、关于 RLM 的工程化说明（重要）

本文档中提及的 RLM（Retrieval / Logic / Memory），  
指 **IS-CGP 场景下的工程化 RLM**。

该 RLM：

- 并非对学术论文中 RLM 推理范式的完整复现
- 不依赖语言模型生成结果作为治理决策依据
- 为 **非生成式、确定性、可审计的治理执行单元**
- 以 **可治理性优先于效果最优** 为设计原则

完整工程定义请参见：

📄 **`docs/rlm_scope.md`**

---

## 五、当前工程重心（Current Focus）

### 🎯 当前阶段目标

IS-CGP 当前阶段不追求平台功能完备，而是专注于：

> **验证工程化 RLM 在长上下文场景下的治理正确性与稳定性**

具体包括：

- 上下文治理流水线（RLM）的工程实现
- 决策轨迹（Decision Trace）的结构化落库
- 长上下文条件下的：
  - 上下文选择
  - 截断策略
  - 可回放能力

当前阶段允许 **Mock 推理后端**，  
重点验证治理行为本身，而非模型效果。

---

## 六、系统架构概览（Architecture）

```

[ 现有聊天 UI / 业务系统 ]
|
（标准 API / SDK）
v
[ IS-CGP 治理层 ]
- 项目 / 会话管理
- 上下文治理流水线（RLM）
- 策略与规则执行
- 决策轨迹与审计
- 缓存治理
|
v
[ 模型推理后端 ]
(llama.cpp / vLLM / others)

```

IS-CGP 与推理引擎 **完全解耦**，  
支持 **全离线内网部署**。

---

## 七、项目状态（Project Status）

🚧 **Active Development**

- 系统定位与工程边界已明确
- 当前仓库为 **Open Core 基础版本**
- 以工程验证与可复现性为优先目标

---

## 八、开发日志（Development Log）

### v0.1.0 — 工程基线与后端骨架（当前）

**目标**  
建立一个 **可重复启动、可审计、可演进** 的治理工程基线。

#### 基础设施

- Docker Compose 本地环境
- PostgreSQL 16（治理元数据）
- Redis 7（缓存占位）
- FastAPI 后端服务
- `/healthz` 健康检查接口

#### 数据库

- Alembic 迁移系统
- 核心表：
  - `projects`
  - `sessions`
  - `users`（预留）
  - `alembic_version`

#### API

- 自动生成 OpenAPI / Swagger
- 已实现：
  - `POST /v1/projects`
  - `GET /v1/projects`
  - `POST /v1/sessions`
  - `GET /v1/sessions`

#### 当前限制

- 尚未引入认证与授权
- Redis 未参与实际治理逻辑
- 无 UI / 控制台

---

## 九、路线图（Roadmap）

- **v0.1**  
  治理工程基线：项目 / 会话模型、基础 API

- **v0.2**  
  工程化 RLM MVP：
  - 上下文治理流水线
  - 决策 Trace 落库
  - 长上下文治理验证

- **v1.0**  
  治理能力产品化：
  - 治理控制台
  - 推理适配器
  - 内网部署与审计手册

---

## 许可证（License）

Apache License 2.0

---

## 名称声明

“IS-CGP（Intelligent Secure Conversation Governance Platform）”为项目名称。  
Fork 或衍生项目不得在未授权情况下使用该名称暗示官方关系。

---

## 维护者（Maintainers）

Maintained by **Ay1men2** and contributors.  
欢迎提交 Issue、设计讨论与工程贡献。
```

---

