# 模块 2: AgentCore Memory

> ⏱️ 预计时间：15 分钟

## 学习目标

- 理解 AgentCore Memory 的概念和用途
- 了解 Memory 的两种策略：User Preference 和 Semantic
- 创建 Memory 并配置策略
- 理解 Memory 如何与 Agent 集成

---

## 2.1 什么是 AgentCore Memory？

AgentCore Memory 是一个托管的记忆服务，让 AI Agent 能够跨会话记住信息。它解决了 LLM 的一个核心限制：**无状态性**。

### 为什么需要 Memory？

没有 Memory 的 Agent：
```
用户: 我喜欢用中文交流
Agent: 好的，我会用中文回复您。

--- 新会话 ---

用户: 帮我查一下保修
Agent: Sure, I can help you check the warranty...  ← 忘记了用户偏好
```

有 Memory 的 Agent：
```
用户: 我喜欢用中文交流
Agent: 好的，我会用中文回复您。

--- 新会话 ---

用户: 帮我查一下保修
Agent: 好的，我来帮您查询保修信息。  ← 记住了用户偏好
```

### Memory 策略类型

| 策略 | 用途 | 示例 |
|------|------|------|
| **User Preference** | 记住用户的偏好设置 | 语言偏好、沟通方式、产品兴趣 |
| **Semantic** | 存储对话中的事实信息 | 用户提到的产品、问题描述、解决方案 |

---

## 2.2 Memory 架构

```
┌─────────────────────────────────────────┐
│           AgentCore Memory              │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  Strategy: User Preference      │    │
│  │  Namespace: support/customer/   │    │
│  │            {actorId}/preferences│    │
│  │                                 │    │
│  │  存储: 语言偏好、沟通方式等     │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  Strategy: Semantic             │    │
│  │  Namespace: support/customer/   │    │
│  │            {actorId}/semantic   │    │
│  │                                 │    │
│  │  存储: 对话事实、产品信息等     │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

- **Namespace** 使用 `{actorId}` 模板变量，实现按用户隔离
- 每个策略独立存储和检索
- 检索时可以配置 `top_k` 和 `relevance_score` 阈值

---

## 2.3 创建 Memory

### 代码解析

打开 `utils/agentcore_helper.py`，查看 `create_agentcore_memory` 函数：

```python
def create_agentcore_memory(name, description, region):
    """创建 AgentCore Memory"""
    memory_manager = MemoryManager(region_name=region)

    memory = memory_manager.get_or_create_memory(
        name=name,
        strategies=[
            {
                # 策略1: 用户偏好
                StrategyType.USER_PREFERENCE.value: {
                    "name": "CustomerPreferences",
                    "description": "Captures customer preferences and behavior",
                    "namespaces": ["support/customer/{actorId}/preferences"],
                }
            },
            {
                # 策略2: 语义记忆
                StrategyType.SEMANTIC.value: {
                    "name": "CustomerSupportSemantic",
                    "description": "Stores facts from conversations",
                    "namespaces": ["support/customer/{actorId}/semantic"],
                }
            },
        ],
    )

    return memory["id"]
```

关键点：
- `get_or_create_memory` 是幂等操作，重复调用不会创建重复资源
- 两个策略使用不同的 namespace 前缀
- `{actorId}` 会在运行时替换为实际的用户 ID

### 手动创建（可选）

如果您想手动体验创建过程：

```python
import boto3
from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager
from bedrock_agentcore.memory.constants import StrategyType

region = "us-east-1"
memory_manager = MemoryManager(region_name=region)

memory = memory_manager.get_or_create_memory(
    name="CustomerSupportMemory",
    strategies=[
        {
            StrategyType.USER_PREFERENCE.value: {
                "name": "CustomerPreferences",
                "description": "Captures customer preferences",
                "namespaces": ["support/customer/{actorId}/preferences"],
            }
        },
        {
            StrategyType.SEMANTIC.value: {
                "name": "CustomerSupportSemantic",
                "description": "Stores conversation facts",
                "namespaces": ["support/customer/{actorId}/semantic"],
            }
        },
    ],
)

print(f"Memory ID: {memory['id']}")
```

> ⏳ Memory 创建大约需要 2-3 分钟。

---

## 2.4 Memory 与 Agent 的集成

在 `agent/customer_support_agent.py` 中，Memory 通过 `AgentCoreMemorySessionManager` 与 Strands Agent 集成：

```python
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

# 配置 Memory
memory_config = AgentCoreMemoryConfig(
    memory_id=MEMORY_ID,
    session_id=session_id,       # 每次对话的唯一 ID
    actor_id="customer_001",     # 用户标识
    retrieval_config={
        # 语义记忆检索配置
        "support/customer/{actorId}/semantic": RetrievalConfig(
            top_k=3,              # 返回最相关的 3 条记录
            relevance_score=0.2   # 相关性阈值
        ),
        # 用户偏好检索配置
        "support/customer/{actorId}/preferences": RetrievalConfig(
            top_k=3,
            relevance_score=0.2
        ),
    },
)

# 创建 Agent 时传入 session_manager
agent = Agent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    session_manager=AgentCoreMemorySessionManager(memory_config, REGION),
)
```

### 工作流程

1. **对话开始** → Memory 自动检索该用户的历史记忆
2. **对话进行** → Agent 正常处理用户请求
3. **对话结束** → Memory 自动提取并存储新的偏好和事实

这一切都是自动完成的，Agent 代码不需要显式调用 Memory API。

---

## 2.5 验证 Memory

创建完成后，可以通过 AWS CLI 验证：

```bash
# 列出所有 Memory
aws bedrock-agentcore-control list-memories --query 'memories[].{name:name, id:memoryId, status:status}'
```

您应该看到：
```json
[
    {
        "name": "CustomerSupportMemory",
        "id": "customersupportmemory-xxxxxxxx",
        "status": "ACTIVE"
    }
]
```

---

## 2.6 关键概念总结

| 概念 | 说明 |
|------|------|
| Memory | 托管的记忆存储服务 |
| Strategy | 记忆提取策略（User Preference / Semantic） |
| Namespace | 记忆的隔离空间，支持模板变量 |
| Actor ID | 用户标识，用于隔离不同用户的记忆 |
| Session ID | 会话标识，用于关联同一次对话 |
| Retrieval Config | 检索配置（top_k、relevance_score） |

---

## ✅ 检查清单

- [ ] 理解 Memory 的两种策略类型
- [ ] 理解 Namespace 和 Actor ID 的作用
- [ ] 了解 Memory 如何与 Strands Agent 集成
- [ ] Memory 创建成功（状态为 ACTIVE）

---

[⬅️ 上一模块: 基础设施部署](./module-01-infrastructure.md) | [下一模块: AgentCore Gateway ➡️](./module-03-gateway.md)
