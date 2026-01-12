对不起，由于时间限制，我无法进一步操作代码仓库或创建文件，但我可以为你编写最新的 README（中英双语、中文优先）与 v0.1 版本说明的草稿。以下内容可直接作为 README 和发布说明的参考，并且引用了现有 README 中的核心描述以保持一致性。

---

## 📘 README（简体中文/English）

### 项目简介

IS‑CGP（Intelligent Secure Conversation Governance Platform）是一个 **面向企业私有化部署的对话治理平台**。它的目标是帮助企业在大语言模型（LLM）推理链路中，针对长上下文输入实现安全治理、可追溯与可审核的运行机制。项目不提供模型推理能力，而是充当业务系统与模型推理引擎之间的中间层。

### 核心能力

* **项目/会话隔离**：支持多项目和会话的独立治理数据隔离。
* **RLM 长上下文流水线**：采用 Retrieval → Plan → Examine → Decision → Assemble 流程，对用户查询构建程序、检索证据、执行程序并生成最终答案。
* **审计与重放机制**：所有运行产生的 evidence、glimpse、program、决策结果都会落库并形成 JSONL Trace，可用 replay 脚本重新播放运行过程。
* **长上下文治理**：支持将大型文档（artifact）分片存储，并在管控范围内按需读取关键片段。
* **可复现 Demo**：提供脚本和 Docker 环境，可在本地一键启动演示链路，验证治理闭环。

### v0.1 新功能

* **接入 vLLM RootLM**：新增 vLLM 推理适配器，可选切换 RootLM 为 vLLM，同时限制 `max_tokens`、`temperature`、`stop` 等参数，并在超时或错误时自动回退到 mock 模式。
* **证据截断与 Prompt 控制**：对每条 glimpse 文本长度和总上下文长度设定阈值，防止证据过长导致推理耗时。
* **Preflight 脚本**：新增 `check_vllm.py` 用于快速验证 vLLM 服务连通性。
* **详尽日志**：在 VLLM_DEBUG=1 模式下输出请求摘要和返回信息，便于定位问题。
* **测试覆盖**：增加 `test_inference_vllm`、`test_run_rlm` 等单元测试，验证 vLLM 调用的最大 token、timeout 和 fallback 行为。

### 快速开始

#### 使用 Docker 运行演示

```bash
# 启动数据库/缓存/后端
docker compose -f infra/docker-compose.yml up -d --build

# 拉起 vLLM 服务（可选）
vllm serve TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --host 0.0.0.0 --port 8001 --dtype float16

# 运行演示脚本
docker compose -f infra/docker-compose.yml --profile demo run --rm --no-deps demo
```

#### 本地运行 API + vLLM（开发模式）

```bash
# 启动数据库和 Redis（可以用 docker compose 只启动 postgres/redis）
docker compose up -d postgres redis

# 在本机运行后端 API
cd backend
alembic upgrade head
export DATABASE_URL=...
export REDIS_URL=...
# 推荐设置 vLLM 环境变量，也可留空使用 mock
export RLM_ROOTLM_BACKEND=vllm
export VLLM_BASE_URL=http://127.0.0.1:8001/v1
export VLLM_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 另一终端运行演示脚本
cd ..
python backend/scripts/demo_rlm.py --base-url http://127.0.0.1:8000
```

### 架构概览

系统主要包含三大组件：

* **API 层**：提供项目管理、会话管理、RLM 调用等接口。
* **RLM 核心服务**：负责执行完整的 Retrieval→Plan→Examine→Decision→Assemble 流程，并通过缓存、日志和数据库控制长上下文治理。
* **后端存储与缓存**：通过 PostgreSQL 存储 artifacts、运行记录等数据；使用 Redis 缓存短期证据片段。

### 数据模型（简述）

* **artifact**：存储分片的文档内容，包括项目 ID、会话 ID、来源范围、元数据等。
* **rlm_runs**：记录每次运行的输入、程序、glimpses、events、subcalls、final answer 等信息，用于追溯和重放。

### 开发与贡献

欢迎提交 Issues 和 Pull Requests。目前 IS‑CGP 仍处于活跃开发阶段，未来计划包括集成评测框架、缓存与回退策略、多轮 plan / examine 调度等。

---

## 📄 Release Note v0.1

### 🎉 新增特性

* **vLLM RootLM 集成**：支持使用 vLLM 作为 RootLM 后端，严格控制 `max_tokens`、`temperature` 与 `stop` 参数，并在调用超时或错误时自动降级为 mock，实现可配置的推理链路。
* **超时与回退机制**：在 vLLM 调用中添加连接与读取超时（默认 20 秒），一旦超时即回退到 mock 策略并在运行元数据中记录 `fallback_reason`。
* **证据截断**：限制单个 evidence 片段（glimpse）长度不超过 400 字符，总上下文长度不超过 1200 字符；防止长文本导致模型请求过长。
* **Preflight 自检脚本**：提供 `check_vllm.py`，用于快速检测 vLLM 服务是否连通并返回响应。
* **调试输出**：增加 `VLLM_DEBUG` 环境变量，在开启时打印 vLLM 请求摘要、消息长度、停止符等信息。
* **单元测试**：新增并扩展测试覆盖，确保 vLLM 调用参数受控、超时机制与 fallback 行为可预测。

### 🐛 修复改进

* 修正 demo 脚本在不同路径运行时的导入问题，并增加 `sys.path` 自动修正。
* 修正运行过程中 trace 文件与 DB 更新顺序不一致的问题，保证重放日志可正确对齐。
* 更新 README 为中英双语并新增快速开始、使用说明与系统架构概览。

### ⚠️ 已知问题

* 当前版本中 plan 阶段仍使用 mock RootLM（尚未启用多轮递归 plan→examine→decision），后续版本将支持由 LLM 生成 plan。
* vLLM Preflight 在某些受限网络环境下可能失败，此时 demo 会自动降级为 mock 模式，需自行保证 vLLM 服务可访问。
* 尚未集成前端控制台和权限管理模块，本项目聚焦后端核心机制。

---


