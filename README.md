
---

# IS-CGP — 智安对话治理平台

**Intelligent Secure Conversation Governance Platform**

---

## 项目定位（Positioning）

**IS-CGP（智安对话治理平台）** 是一个面向 **内网 / 私有化部署场景** 的
**大模型会话治理中间层（Governance Middleware, Open Core）**。

本项目不追求“平台功能完备”，而是聚焦于一个核心问题：

> **当大模型被真实组织长期、多角色、多项目使用时，
> 我们如何让“上下文进入模型的过程”变得可治理、可解释、可审计？**

IS-CGP 以 **不侵入底层推理引擎** 为前提，为现有聊天系统与模型服务提供统一的治理能力，而非替代它们。

> **EN**
> IS-CGP is an open-core governance middleware that focuses on making LLM context assembly auditable, controllable, and reproducible in on-premise environments.

---

## 一、背景与动机（Why）

### 中文

随着大模型在 **政务、医疗、科研机构等内网环境** 中逐步落地，其使用形态正在从“个人试验”演化为：

> **多项目 / 多部门 / 多角色的长期共享基础设施**

在这一阶段，系统瓶颈不再主要体现在模型推理性能或算力利用率，而是集中暴露在 **治理层面**：

* 多项目并行使用下，**上下文与数据隔离不足**
* 内部制度文件、科研资料、源代码等资产
  **难以按角色与保密等级进行精细化控制**
* 模型输出结果缺乏清晰的 **可审计、可解释路径**
* 检索与缓存机制在策略或权限变化后
  **缺乏统一、可靠的失效与追责机制**
* 在 **长上下文（Long Context）** 场景下：

  * “给多少上下文”
  * “给哪些上下文”
  * “出问题责任如何界定”
    往往没有系统化答案

现有方案多聚焦于推理效率或应用层能力，而 **缺乏一个独立、工程化的治理中间层**。

IS-CGP 正是在这一背景下提出，用于补齐 **内网大模型基础设施中的治理能力短板**。

### EN (Brief)

As LLMs become shared infrastructure, governance—not inference—becomes the core challenge. IS-CGP focuses on auditable context control and long-context governance in on-prem environments.

---

## 二、IS-CGP 是什么（What）

### 中文

IS-CGP 定位为 **大模型服务的治理中间层**，部署在：

```
现有聊天 UI / 业务系统
          ↓
        IS-CGP
          ↓
   模型推理后端
(llama.cpp / vLLM / others)
```

它 **不绑定 UI、不替代模型、不干预推理实现**，而是为所有模型调用提供统一的治理能力。

---

### 核心能力（Capability-Oriented）

* **会话与项目级隔离**

  * Session / Project 作为最小治理单元
  * 防止跨项目、跨任务的上下文污染

* **策略驱动的上下文拼装（Context Governance）**

  * 按规则、策略与状态决定：

    * 哪些信息可被检索
    * 哪些信息可进入模型上下文
    * 哪些信息只能作为“证据”而非 Prompt 内容

* **RLM 风格的上下文治理流水线**

  * 采用 RLM（Reasoning / Retrieval / Logic / Memory）作为工程语义参考
  * **不主张 RLM 概念创新**
  * 聚焦其在治理系统中的 **工程化实现与可解释执行**

* **审计与证据链（Audit & Evidence Trace）**

  * 记录每一次上下文选择的依据
  * 支持事后审计、问题回溯与责任界定

* **长上下文治理与缓存约束**

  * 在长上下文场景下：

    * 控制上下文规模
    * 约束缓存复用
    * 保证策略变更后的可靠失效

> **EN (Summary)**
> IS-CGP focuses on auditable context governance rather than UI, inference, or model training.

---

## 三、IS-CGP 不是什么（What IS-CGP Is NOT）

为避免误解，IS-CGP **明确不承担** 以下职责：

* ❌ 模型训练、微调或推理优化框架
* ❌ Agent / Planner / AutoGPT 系统
* ❌ 聊天 UI 或前端产品
* ❌ 公网 SaaS 或多租户托管服务
* ❌ 无边界共享 KV Cache 的性能优先系统

IS-CGP 优先保证 **治理正确性、可解释性与审计可靠性**，而非激进的性能复用。

---

## 四、当前研究与工程重心（Current Focus）

### 🎯 当前阶段目标

IS-CGP 当前阶段 **不追求平台功能完备**，而是专注于一个可验证的工程目标：

> **验证并实现一套“可治理的上下文拼装与长上下文控制机制”**

具体聚焦于：

* RLM 风格的上下文治理流水线（工程实现）
* 长上下文场景下的上下文选择、截断与记录
* 与推理引擎解耦的治理逻辑验证

这一阶段允许 **Mock 推理后端**，重点验证治理行为本身。

---

## 五、系统架构概览（Architecture）

```
[ 现有聊天 UI / 业务系统 ]
              |
        （标准 API / SDK）
              v
        [ IS-CGP 治理层 ]
        - 会话 / 项目管理
        - 上下文治理流水线（RLM-style）
        - 策略与规则引擎
        - 审计与证据链
        - 缓存治理
              |
              v
      [ 模型推理后端 ]
   (llama.cpp / vLLM / others)
```

IS-CGP 与推理引擎 **完全解耦**，支持 **全离线内网部署**。

---

## 六、项目状态（Project Status）

🚧 **Active Development**

* 系统定位与工程边界已明确
* 当前仓库为 **Open Core 基础版本**
* 以工程验证与可复现性为优先目标

---

## 七、开发日志（Development Log）

### v0.1.0 — 工程基线与后端骨架（当前）

**目标**
建立一个 **可重复启动、可审计、可演进** 的治理工程基线。

#### 基础设施

* Docker Compose 本地环境
* PostgreSQL 16（治理元数据）
* Redis 7（缓存占位）
* FastAPI 后端
* `/healthz` 健康检查

#### 数据库

* Alembic 迁移系统
* 核心表：

  * `projects`
  * `sessions`
  * `users`（预留）
  * `alembic_version`

#### API

* 自动生成 OpenAPI
* 已实现：

  * `POST /v1/projects`
  * `GET /v1/projects`
  * `POST /v1/sessions`
  * `GET /v1/sessions`

#### 当前限制

* 尚未引入认证与授权
* Redis 未参与实际治理逻辑
* 无 UI / 控制台

---

## 八、路线图（Roadmap）

* **v0.2**

  * RLM 风格上下文治理 MVP
  * 长上下文工程验证
  * 决策 Trace 落库
* **v1.0**

  * 治理控制台
  * 推理适配器
  * 内网部署与审计手册

---

## 九、关于 RLM 的声明（Important Note）

RLM（Reasoning / Retrieval / Logic / Memory）作为一种研究语义已在既有工作中提出。

**IS-CGP 不主张对 RLM 概念本身的创新或所有权**，
而是专注于其在 **治理系统中的工程化实现、约束与审计能力**。

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
欢迎 Issue、设计讨论与工程贡献。

---




