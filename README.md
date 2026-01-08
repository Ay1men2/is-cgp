好，这一版我会**进一步“本地化”**，目标很明确：

> **这是一个“给中国内网场景、研究所/单位/工程评审看”的 README**
> 英文是配套说明，不是主叙事。

我会做到三点：

* **中文优先、英文从属**（而不是中英对照硬翻）
* **工程 / 治理语境**，避免产品宣传腔
* **不超出当前实现能力**，但为后续演进留接口

下面是**可直接整体替换的 README 最终版（CN-first, bilingual）**。

---

# IS-CGP — 智安对话治理平台

**Intelligent Secure Conversation Governance Platform**

---

## 项目简介

**IS-CGP（智安对话治理平台）** 是一个面向 **内网私有化部署场景** 的 **大模型会话治理中间层（Open Core）**。

本项目以“不侵入底层推理引擎”为前提，围绕 **会话隔离、访问控制、可审计上下文拼装与缓存治理** 等核心问题，为研究所、政务、医疗及其他高合规要求单位提供一套 **可落地、可审计、可演进** 的大模型治理能力。

> **EN**
> IS-CGP is an open-core governance middleware for secure, auditable, and controllable LLM conversations in on-premise / private-network environments.

---

## 一、背景与动机（Why）

### 中文

随着大模型在 **研究所、政务、医疗等内网环境** 中逐步落地，其使用形态正从早期的“个人试验”转向“**多项目、多部门、多角色共享使用**”。

在这一阶段，系统瓶颈不再主要体现在模型推理性能或算力利用率，而是集中暴露在 **治理层面**：

* 多项目、多部门并行使用下，**上下文与数据隔离不足**；
* 内部制度文件、科研资料、源代码等资产，**难以按角色与保密等级精细控制**；
* 模型输出缺乏清晰的 **可审计、可解释路径**；
* 缓存与加速机制在权限、策略或知识变更后，**缺乏统一、可靠的失效机制**。

现有大模型部署方案普遍聚焦推理效率，但 **缺乏独立、系统化的治理中间层**。
IS-CGP 正是在这一背景下提出，目标是补齐内网大模型基础设施中的“治理能力短板”。

### EN (Brief)

As LLM usage shifts to multi-project and multi-role shared deployments, governance—not inference performance—becomes the primary bottleneck. IS-CGP addresses isolation, access control, auditability, and cache consistency in on-prem environments.

---

## 二、IS-CGP 是什么（What）

### 中文

IS-CGP 定位为 **大模型服务的治理中间层**，部署在 **现有聊天 UI / 业务系统** 与 **模型推理后端**（如 `llama.cpp`、`vLLM`）之间。

它不替代模型、不绑定 UI，而是为所有大模型调用提供统一的治理能力。

### 核心能力

* **会话与项目级上下文管理**
  Session / Project 作为最小隔离单元，避免跨项目上下文污染。

* **策略驱动的上下文拼装**
  按策略对上下文进行过滤、脱敏，或仅允许检索而不进入 Prompt。

* **分级保密与访问控制**
  基于 RBAC 与安全标签（Security Labels）的访问控制模型。

* **提示词配方库（Prompt Recipes）**
  面向高频、规范化场景的提示词模板，**授权可选**，而非黑箱替换用户输入。

* **审计与证据链（Audit & Evidence Trace）**
  记录模型回答所依赖的资料来源、策略决策、过滤记录与缓存使用情况。

* **多级缓存治理**
  统一管理检索缓存、前缀缓存及可选 KV Cache，并支持策略与权限变更后的可靠失效。

### EN (Summary)

IS-CGP is a governance capability layer providing session isolation, policy-driven context assembly, access control, auditability, and cache governance—without modifying the inference engine.

---

## 三、IS-CGP 不是什么（What IS-CGP Is NOT）

为避免误解，IS-CGP **明确不承担** 以下职责：

* ❌ 模型训练或参数微调框架
* ❌ 聊天 UI 或前端系统的替代品
* ❌ 公网 SaaS 或云端托管服务
* ❌ 跨部门 / 跨租户自由共享 KV Cache 的系统

IS-CGP 优先考虑 **内网安全性、治理正确性与可审计性**，而非激进的性能复用。

---

## 四、界面与接入策略（UI & Integration）

IS-CGP 采用 **“两套界面 + 一套标准接口”** 的策略，避免与现有系统冲突。

### 1️⃣ 治理控制台（必需）

面向管理员与运维人员，用于：

* 项目、角色与权限管理
* 保密等级与策略配置
* 提示词配方库维护
* 缓存监控与失效操作
* 审计查询与会话回放

### 2️⃣ 参考聊天 UI（可选）

* 用于能力验证与演示
* 展示证据链与审计信息
* 不作为核心依赖组件

### 3️⃣ 标准 API / SDK（核心资产）

* 无侵入接入现有聊天 UI、业务系统或内部工具
* 治理能力通过 API 统一暴露

---

## 五、系统架构概览（Architecture）

```
[ 现有聊天 UI / 业务系统 ]
              |
        （标准 API / SDK）
              v
        [ IS-CGP 网关层 ]
        - 会话 / 项目管理
        - 策略与安全标签
        - 上下文拼装器
        - 提示词配方
        - 审计与证据链
        - 缓存治理
              |
              v
      [ 模型推理后端 ]
   (llama.cpp / vLLM / 其他)
```

IS-CGP 与具体推理引擎解耦，支持 **完全离线部署**。

---

## 六、身份体系与部署模式

IS-CGP 通过统一抽象支持多种身份来源：

* **MVP 阶段**：本地账号体系
* **典型内网部署**：通过反向代理 / 网关透传身份信息
* **扩展场景**：支持 OIDC / SAML（可选）

治理核心逻辑不依赖具体身份实现。

---

## 七、项目状态（Project Status）

🚧 **持续开发中（Active Development）**

* 核心概念与系统定位已稳定
* 按里程碑逐步实现治理能力
* 当前仓库为 **Open Core 基础版本**

---

## 八、开发日志（Development Log）

### v0.1.0 — 基础设施与后端骨架（当前）

**目标**
建立一个 **可重复启动、可审计、可演进** 的工程基线。

#### 基础设施

* 基于 Docker 的本地开发环境
* PostgreSQL 16（治理元数据）
* Redis 7（缓存占位）
* FastAPI 后端服务
* `docker compose` 一键启动
* `/healthz` 健康检查接口

#### 数据库与迁移

* Alembic 迁移系统已接入
* 核心表结构：

  * `projects`（项目隔离单元）
  * `sessions`（会话实例）
  * `users`（身份预留）
  * `alembic_version`

#### 后端 API

* FastAPI 应用骨架稳定
* 自动生成 OpenAPI / Swagger
* 已实现接口：

  * `POST /v1/projects`（按名称幂等创建）
  * `GET /v1/projects`
  * `POST /v1/sessions`
  * `GET /v1/sessions`
* 显式 UUID 序列化，避免隐式类型问题

#### 当前限制

* 尚未引入身份认证与授权
* Redis 未参与实际缓存治理
* 治理控制台与 UI 尚未实现

---

## 九、下一阶段计划（v0.2 预告）

* JWT 用户认证
* 项目级 RBAC 权限控制
* 消息模型与基础聊天接口
* 面向治理的上下文拼装骨架

---

## 十、路线图（Roadmap）

* **v0.1**：核心数据模型与后端骨架
* **v0.2**：上下文治理、缓存治理、控制台 MVP
* **v1.0**：内网部署手册、推理适配器、评估指标

---

## 许可证（License）

本项目采用 **Apache License 2.0**。

---

## 名称与声明

“IS-CGP（Intelligent Secure Conversation Governance Platform）”为项目名称。
Fork 或衍生项目不得在未授权情况下使用该名称暗示官方关系。

---

## 维护者（Maintainers）

Maintained by **Ay1men2** and contributors.
欢迎提交 Issue、讨论设计与贡献代码。

---

## 快速开始（开发态）

> TODO：docker-compose + backend 启动说明

---

### 说一句直白的评价

这版 README：

* **非常“中国内网项目气质”**
* 可以直接给 **研究所、信息中心、导师、工程评审** 看
* 不会被质疑“PPT 项目”或“空谈平台”

如果你愿意，下一步我可以帮你做三件**极其加分**的事之一：

1️⃣ 写一页 **《核心概念与术语定义（审计/治理视角）》**
2️⃣ 把 **一次请求的完整治理时序**画成文字版流程
3️⃣ 帮你把 **缓存失效规则**写成接近“制度条款”的形式

你选一个，我们继续把 IS-CGP 往“真正能立项”的方向推。

