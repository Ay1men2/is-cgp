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

