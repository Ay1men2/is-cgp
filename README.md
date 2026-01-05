# IS-CGP（Intelligent Secure Conversation Governance Platform）

IS-CPG 是一套面向 **内网 / 私有化大模型部署** 的对话治理中间层，
用于解决多角色、多项目、多安全等级场景下的大模型 **上下文拼装、权限控制、审计与缓存治理** 问题。

## 核心目标（MVP）
- 会话级 / 片段级安全分级（Security Label）
- 可审计的上下文拼装（Evidence Trace）
- 面向 LLM 推理后端的治理中间层（Adapter 模式）
- 支持内网部署（Docker / 私有环境）

## 仓库结构
# IS-CPG
backend/ # 治理中间层（FastAPI）
admin-console/ # 管理员治理控制台（Web）
chat-ui/ # 示例聊天界面（可选）
sdk/ # 接入 SDK（后置）
docs/ # 架构与设计文档
infra/ # Docker / 部署配置
scripts/ # 工具与脚本


## 快速开始（开发态）
> TODO: docker-compose + backend 启动

