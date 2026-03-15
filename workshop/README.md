# Amazon Bedrock AgentCore 端到端实战 Workshop

## 🎯 Workshop 概述

在这个 Workshop 中，您将从零开始构建一个完整的 AI 客服系统，深入体验 Amazon Bedrock AgentCore 的核心能力。通过动手实践，您将学会如何使用 AgentCore 的 Runtime、Gateway、Memory、Policy Engine 等组件，构建一个具备工具调用、记忆管理、访问控制和实时可视化的生产级 AI Agent 应用。

### 您将构建什么？

一个电子产品客服 AI Agent，具备以下能力：
- 🤖 基于 Claude 模型的智能对话
- 🔧 通过 Gateway 调用多种工具（保修查询、网页搜索、代金券批复）
- 🧠 通过 Memory 记住用户偏好和对话历史
- 🛡️ 通过 Policy Engine 控制工具访问权限（如限制代金券金额）
- 📊 通过 React 前端实时可视化 Agent 工作流
- 🔐 通过 Cognito 实现用户认证

### 架构图

```
┌─────────────┐
│  React 前端  │ ← Cognito 认证
│  (CloudFront)│
└──────┬──────┘
       │
┌──────▼──────┐
│  AgentCore   │
│   Runtime    │ ← 生产级部署 + Streaming
└──────┬──────┘
       │
┌──────▼──────┐     ┌──────────────┐
│  Strands     │────▶│ AgentCore    │
│  Agent       │     │ Memory       │
└──────┬──────┘     └──────────────┘
       │
┌──────▼──────┐     ┌──────────────┐
│  AgentCore   │────▶│ AgentCore    │
│  Gateway     │     │ Policy Engine│
└──────┬──────┘     └──────────────┘
       │
┌──────▼──────────────────────────┐
│         Lambda 工具              │
│  ┌─────────┐ ┌────────┐ ┌─────┐│
│  │Warranty │ │Web     │ │Coupon││
│  │Check    │ │Search  │ │Tool  ││
│  └─────────┘ └────────┘ └─────┘│
└─────────────────────────────────┘
```

### 预计时间

| 模块 | 时间 |
|------|------|
| 模块 0: 环境准备（含 Event Studio） | 15 分钟 |
| 模块 1: 基础设施部署 | 15 分钟 |
| 模块 2: AgentCore Memory | 15 分钟 |
| 模块 3: AgentCore Gateway | 20 分钟 |
| 模块 4: Policy Engine | 15 分钟 |
| 模块 5: AgentCore Runtime | 20 分钟 |
| 模块 6: 前端可视化 | 15 分钟 |
| 模块 7: 端到端测试 | 15 分钟 |
| 模块 8: 清理资源 | 10 分钟 |
| **总计** | **约 2.5 小时** |

### 前置知识

- 基本的 AWS 使用经验
- Python 基础
- 了解 AI/LLM 基本概念（非必须）

### AWS 服务

本 Workshop 涉及以下 AWS 服务：
- Amazon Bedrock（Claude 模型）
- Amazon Bedrock AgentCore（Runtime、Gateway、Memory、Policy Engine）
- Amazon Cognito（用户认证）
- AWS Lambda（工具函数）
- Amazon DynamoDB（数据存储）
- Amazon S3 + CloudFront（前端托管）
- AWS CloudFormation（基础设施即代码）
- AWS Systems Manager Parameter Store（配置管理）

---

## 📚 目录

- [模块 0: 环境准备](./module-00-prerequisites.md)
- [模块 1: 基础设施部署](./module-01-infrastructure.md)
- [模块 2: AgentCore Memory](./module-02-memory.md)
- [模块 3: AgentCore Gateway](./module-03-gateway.md)
- [模块 4: Policy Engine](./module-04-policy.md)
- [模块 5: AgentCore Runtime](./module-05-runtime.md)
- [模块 6: 前端可视化](./module-06-frontend.md)
- [模块 7: 端到端测试](./module-07-testing.md)
- [模块 8: 清理资源](./module-08-cleanup.md)

---

> ⚠️ **重要提示**：本 Workshop 会创建 AWS 资源并产生费用。请在完成后按照模块 8 清理所有资源。
