# IS-CGP — Intelligent Secure Conversation Governance Platform  
# 智安对话治理平台

**IS-CGP** is an **open-core governance layer** for **secure, auditable, and controllable LLM conversations** in **on-premise / private-network environments**.

**IS-CGP（智安对话治理平台）** 是一个面向 **内网私有化部署** 的 **大模型会话治理中间层（Open Core）**，用于在不侵入底层推理引擎的前提下，实现 **安全隔离、可审计、可控上下文拼装与缓存治理**。

---

## Why IS-CGP / 为什么需要 IS-CGP

As LLM services move from **single-user experimentation** to **multi-project / multi-role shared usage** in research institutes, government, and healthcare environments, performance alone is no longer the primary bottleneck.

随着大模型在 **研究所、政务、医疗等内网环境** 中的使用不断扩大，模型服务形态正从“单人试验”转向“多项目、多角色共享使用”，真实瓶颈逐渐转向治理层面：

- **Isolation & Access Control**  
  Prevent cross-project or cross-department data leakage.  
  **隔离与访问控制**：防止跨项目、跨部门的上下文与资料串用。

- **Auditability & Explainability**  
  Be able to answer *why* a response was produced and *what* it relied on.  
  **可审计与可解释**：回答是否可追溯、是否越权、是否合规。

- **Cache Governance & Consistency**  
  Safely reuse computation results while ensuring correct invalidation.  
  **缓存治理与一致性**：在权限、策略或知识更新后可靠失效，避免错误复用。

Existing LLM stacks focus on inference performance, but **lack a first-class governance layer**.  
IS-CGP is designed to fill this gap.

---

## What IS-CGP Is / IS-CGP 是什么

IS-CGP is a **capability layer** that sits **between your existing UI/business systems and the LLM inference backend** (e.g. llama.cpp, vLLM).

IS-CGP 以“治理中间层”的形式插入在 **现有聊天 UI / 业务系统** 与 **模型推理服务** 之间，提供以下核心能力：

- **Session & Project Context Management**  
  会话与项目级上下文管理

- **Policy-driven Context Assembly**  
  策略驱动的上下文拼装（过滤 / 脱敏 / 仅检索不入 prompt）

- **Security Labels & Access Control**  
  分级保密与访问控制（RBAC + Security Labels）

- **Prompt Recipe Library**  
  提示词配方库（按部门 / 保密等级授权，而非黑箱替换用户问题）

- **Audit & Evidence Trace**  
  审计与证据链（引用来源、过滤记录、策略决策、缓存使用情况）

- **Multi-level Cache Governance**  
  多级缓存治理（检索缓存 / 前缀缓存 / 可选 KV Cache 插件）

---

## What IS-CGP Is NOT / IS-CGP 不是什么

To avoid confusion, IS-CGP explicitly does **not** aim to be:

- ❌ A model training or fine-tuning framework  
  ❌ 模型训练或微调框架

- ❌ A replacement for your existing chat UI  
  ❌ 聊天 UI 的替代品

- ❌ A hosted SaaS or cloud service  
  ❌ 云端 SaaS 服务

- ❌ A system that freely shares KV cache across tenants or departments  
  ❌ 默认不支持跨租户 / 跨部门 KV Cache 共享（内网安全优先）

---

## UI Strategy / 界面策略（不与现有系统冲突）

IS-CGP follows a **“two interfaces + one standard API”** design:

IS-CGP 采用 **“两套界面 + 一套标准接口”** 的策略，避免与现有系统冲突：

1. **Admin Console (Required)**  
   Governance UI for policies, security labels, prompt recipes, audit, and cache operations.  
   **治理控制台（必需）**：策略、标签、提示词配方、审计与缓存管理。

2. **Reference Chat UI (Optional)**  
   A lightweight demo UI for quick trials and evidence visualization.  
   **参考聊天 UI（可选）**：用于能力验证与证据展示。

3. **Standard API / SDK (Core Asset)**  
   Integrate IS-CGP into any existing UI or business system.  
   **标准 API / SDK（核心资产）**：可无侵入接入任何现有系统。

---

## Architecture Overview / 架构概览
[ Existing UI / Business Systems ]
|
|  (Standard API / SDK)
v
[ IS-CGP Gateway ]
	•	Session & Project
	•	Policy & Security Labels
	•	Context Assembler
	•	Prompt Recipes
	•	Audit & Evidence Trace
	•	Cache Governance
|
v
[ Inference Backend ]
(llama.cpp / vLLM / others)


IS-CGP is **inference-backend agnostic** and can be deployed in fully offline environments.

---

## Identity & Deployment Model / 身份与部署模型

IS-CGP supports multiple identity sources through a unified abstraction:

- **MVP**: Local accounts  
- **Typical On-Prem Deployment**: Upstream identity via reverse proxy / gateway headers  
- **General Enterprise Adoption**: OIDC / SAML (optional, extensible)

Core governance logic is independent of the identity provider.

---

## Project Status / 项目状态

🚧 **Active Development**

- Core concepts and architecture are stabilized  
- Implementation is progressing in iterative milestones  
- This repository represents the **open-core foundation**

---

Development Log / 开发日志（中英双语）
v0.1.0 — Infrastructure & Backend Skeleton (Current)

This milestone establishes a reproducible, auditable development baseline for IS-CGP.
本阶段目标是建立一个可重复启动、可审计、可演进的工程基线。

🧱 Infrastructure & Environment

基础设施与开发环境

EN

Docker-based local development environment is fully set up.

Services included:

PostgreSQL 16 (metadata & governance state)

Redis 7 (cache placeholder)

FastAPI backend service

One-command startup via docker compose.

Health check endpoint verifies DB & Redis connectivity.

中文

已完成基于 Docker 的本地开发环境搭建。

当前包含服务：

PostgreSQL 16（治理元数据与状态存储）

Redis 7（缓存占位，后续用于多级缓存治理）

FastAPI 后端服务

支持通过 docker compose 一键启动。

提供 /healthz 接口用于验证数据库与 Redis 连通性。

🗄️ Database & Migration System

数据库与迁移系统

EN

Alembic migration system is fully wired to DATABASE_URL.

Database schema initialized and versioned.

Current core tables:

projects — logical isolation unit

sessions — conversation sessions under projects

users — reserved for upcoming authentication

alembic_version

Migrations can be executed and inspected inside containers.

中文

已完整接入 Alembic 数据库迁移系统，并绑定 DATABASE_URL。

数据库结构已初始化并纳入版本控制。

当前核心数据表包括：

projects —— 项目级隔离单元

sessions —— 项目下的会话实例

users —— 为后续身份认证预留

alembic_version

支持在容器内执行与检查迁移状态。

🌐 Backend API (FastAPI)

后端 API（FastAPI）

EN

FastAPI application skeleton is stabilized.

OpenAPI schema and Swagger UI are automatically generated.

Core API endpoints implemented:

Projects

GET /v1/projects — list recent projects (debug-friendly)

POST /v1/projects — idempotent project creation by name

Sessions

GET /v1/sessions — list recent sessions

POST /v1/sessions — create session under an existing project

UUID handling and response serialization are normalized for API safety.

中文

FastAPI 后端骨架已稳定成型。

自动生成 OpenAPI 文档与 Swagger UI。

已实现的核心接口包括：

项目（Projects）

GET /v1/projects —— 列出最近项目（便于调试）

POST /v1/projects —— 按名称幂等创建项目

会话（Sessions）

GET /v1/sessions —— 列出最近会话

POST /v1/sessions —— 在指定项目下创建会话

已对 UUID 与返回结果进行显式序列化，避免隐式类型问题。

🔍 Observability & Debugging

可观测性与调试支持

EN

OpenAPI schema (/openapi.json) verified to reflect runtime routes.

Explicit DB inspection workflows documented and tested.

Backend and database consistency verified across container restarts.

中文

已验证 /openapi.json 与运行时路由完全一致。

明确了后端 / 数据库双侧调试方式。

在多次容器重建后验证数据与行为一致性。

📐 Architectural Decisions (So Far)

当前阶段的关键设计决策

EN

IS-CGP is implemented as a governance middleware, not an inference engine.

No ORM coupling at this stage; SQL is kept explicit for audit clarity.

Backend is identity-agnostic by design; authentication is layered, not baked in.

中文

IS-CGP 明确定位为治理中间层，而非推理引擎。

当前阶段避免 ORM 黑箱，采用显式 SQL 以保证审计可读性。

后端在架构上与身份源解耦，认证作为可插拔能力引入。

⚠️ Notes & Limitations

注意事项与当前限制

EN

Authentication & authorization are not yet enforced (planned next).

Redis is not yet used for actual cache governance.

Admin Console and UI are not implemented at this stage.

中文

当前尚未引入身份认证与权限控制（下一阶段重点）。

Redis 尚未参与实际缓存治理逻辑。

治理控制台与 UI 尚未实现。

🔜 Next Milestone (v0.2 Preview)

下一阶段预告（v0.2）

EN

User authentication (JWT-based)

Project-level RBAC

Message model and chat stub

Governance-oriented context assembly skeleton

中文

用户认证（JWT）

项目级 RBAC 权限控制

消息模型与基础聊天接口

面向治理的上下文拼装骨架

## Roadmap (High-level) / 路线图（简要）

- **v0.1**  
  Core data model, policy skeleton, audit & evidence schema

- **v0.2**  
  Context assembler, cache governance, admin console MVP

- **v1.0**  
  On-prem deployment playbook, inference adapters, evaluation metrics

---

## License / 许可证

This project is licensed under the **Apache License 2.0**.  
See the `LICENSE` file for details.

---

## Name & Trademark Notice / 名称声明

“IS-CGP” (Intelligent Secure Conversation Governance Platform) is the project name.  
Forks or derivative works must not use the name “IS-CGP” in a way that implies endorsement or an official relationship without permission.

---

## Maintainer / 维护者

Maintained by **Ay1men2** and contributors.

Contributions, issues, and design discussions are welcome.

## 快速开始（开发态）
> TODO: docker-compose + backend 启动

