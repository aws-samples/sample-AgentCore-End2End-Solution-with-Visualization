# 模块 5: AgentCore Runtime

> ⏱️ 预计时间：20 分钟

## 学习目标

- 理解 AgentCore Runtime 的作用和部署流程
- 了解 Runtime 如何容器化 Agent 代码
- 理解 Agent 的完整调用链路
- 部署 Runtime 并等待就绪

---

## 5.1 什么是 AgentCore Runtime？

AgentCore Runtime 是一个托管的 Agent 执行环境。它将您的 Agent 代码打包为容器镜像，部署到 AWS 管理的基础设施上，提供：

- 🚀 **生产级部署** - 自动扩缩容、高可用
- 📡 **HTTP API** - 标准的 REST 端点，支持 Streaming
- 🔐 **认证集成** - 支持 JWT 认证
- 📊 **可观测性** - 自动集成 CloudWatch 和 X-Ray
- 🔄 **版本管理** - 支持更新和回滚

### 部署流程

```
Agent 代码 + requirements.txt
         │
         ▼
┌─────────────────┐
│  AgentCore CLI  │ ← configure + launch
│  (Starter Kit)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   CodeBuild     │ ← 构建 Docker 镜像
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      ECR        │ ← 存储镜像
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AgentCore      │ ← 部署并运行
│  Runtime        │
└─────────────────┘
```

---

## 5.2 Agent 代码结构

### 入口文件 (`agent/customer_support_agent.py`)

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# 初始化 Runtime App
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context=None):
    """AgentCore Runtime 入口点"""
    user_input = payload.get("prompt", "")
    
    # 1. 获取用户认证信息
    request_headers = context.request_headers or {}
    user_auth_header = request_headers.get("Authorization", "")
    
    # 2. 获取 Gateway 配置
    gateway_id = ssm.get_parameter(Name="...")["Parameter"]["Value"]
    
    # 3. 获取 Machine Client token（用于调用 Gateway）
    machine_token = get_machine_token()
    
    # 4. 配置 Memory
    memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id="customer_001",
    )
    
    # 5. 创建 MCP Client 连接 Gateway
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {machine_token}"}
        )
    )
    
    # 6. 创建 Agent
    agent = Agent(
        model=model,
        tools=local_tools + gateway_tools,
        system_prompt=SYSTEM_PROMPT,
        session_manager=AgentCoreMemorySessionManager(memory_config, REGION),
    )
    
    # 7. 执行并返回结果
    response = agent(user_input)
    return {"response": final_text, "events": trace_events}

if __name__ == "__main__":
    app.run()
```

### 本地工具 (`agent/tools.py`)

Agent 有 3 个本地工具（不经过 Gateway）：

```python
@tool
def get_product_info(product_type: str) -> str:
    """获取产品规格信息"""
    # 从内存中的产品数据库查询
    ...

@tool
def get_return_policy(product_category: str) -> str:
    """获取退货政策"""
    # 从内存中的政策数据库查询
    ...

@tool
def get_technical_support(issue_description: str) -> str:
    """从 Knowledge Base 获取技术支持"""
    # 调用 Bedrock Knowledge Base
    ...
```

### Gateway 工具（通过 Gateway 调用）

```python
@tool
def check_warranty_status(serial_number: str) -> str:
    """通过 Gateway 查询保修状态"""
    result = mcp_client.call_tool_sync(
        name="LambdaTools___check_warranty_status",
        arguments={"serial_number": serial_number}
    )
    return str(result)

@tool
def web_search(keywords: str) -> str:
    """通过 Gateway 搜索网页"""
    ...

@tool
def CouponTool(amount: int) -> str:
    """通过 Gateway 批复代金券"""
    ...
```

---

## 5.3 完整调用链路

当用户发送 "I need a $100 coupon" 时：

```
1. 前端 → Runtime API（Bearer token: Web Client JWT）
   │
2. Runtime 解析请求，获取 user_input
   │
3. Runtime 用 Machine Client credentials 获取 M2M token
   │
4. Runtime 创建 MCP Client（使用 M2M token）
   │
5. Memory 检索用户历史记忆
   │
6. Agent（Claude）分析请求，决定调用 CouponTool(amount=100)
   │
7. MCP Client → Gateway（M2M token）
   │
8. Gateway → Policy Engine 评估
   │   Cedar: context.input.amount(100) < 500 → ALLOW ✅
   │
9. Gateway → CouponTool Lambda
   │
10. Lambda 返回: {"success": true, "coupon_code": "COUPON-10000"}
    │
11. Agent 生成最终回复
    │
12. Memory 存储对话事实
    │
13. Runtime 返回响应 + trace events → 前端
```

---

## 5.4 部署 Runtime

### 配置

```python
runtime = Runtime()

runtime.configure(
    entrypoint="agent/customer_support_agent.py",
    execution_role=runtime_role_arn,
    auto_create_ecr=True,
    requirements_file="agent/requirements.txt",
    region=region,
    agent_name="customer_support_agent",
    authorizer_configuration={
        "customJWTAuthorizer": {
            "allowedClients": [machine_client_id, web_client_id],
            "discoveryUrl": discovery_url,
        }
    },
    request_header_configuration={
        "requestHeaderAllowlist": [
            "Authorization",  # 传递用户 token
        ]
    },
)
```

### 启动

```python
launch_result = runtime.launch(
    env_vars={"MEMORY_ID": memory_id},  # 环境变量
    auto_update_on_conflict=True,        # 自动更新已存在的 Runtime
)

runtime_arn = launch_result.agent_arn
```

> ⏳ Runtime 部署大约需要 5-10 分钟（包括 CodeBuild 构建和容器部署）。

### 关键配置说明

| 配置 | 说明 |
|------|------|
| `entrypoint` | Agent 代码入口文件 |
| `execution_role` | Runtime 使用的 IAM Role |
| `auto_create_ecr` | 自动创建 ECR 仓库 |
| `authorizer_configuration` | JWT 认证配置 |
| `requestHeaderAllowlist` | 允许传递到 Agent 的请求头 |
| `env_vars` | 环境变量（如 MEMORY_ID） |

---

## 5.5 Runtime API

部署完成后，Runtime 提供以下 API：

### 调用端点

```
POST https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{runtime_arn}/invocations?qualifier=DEFAULT
```

### 请求格式

```json
{
  "prompt": "I need a $100 coupon"
}
```

### 请求头

```
Content-Type: application/json
Authorization: Bearer {jwt_token}
```

### 响应格式

```json
{
  "response": "I've processed your coupon request...",
  "events": [
    {"type": "user_input", "data": {"node_id": "user", "message": "..."}},
    {"type": "runtime_start", "data": {"node_id": "runtime", "status": "processing"}},
    {"type": "agent_start", "data": {"node_id": "agent", "status": "thinking"}},
    {"type": "gateway_routing", "data": {"node_id": "gateway", "tool": "CouponTool"}},
    {"type": "policy_check", "data": {"node_id": "policy", "status": "checking"}},
    {"type": "tool_call", "data": {"node_id": "tool-coupon", "status": "calling"}},
    {"type": "response", "data": {"content": "...", "status": "complete"}}
  ],
  "streaming": true
}
```

---

## 5.6 验证 Runtime

```bash
# 列出所有 Runtime
aws bedrock-agentcore-control list-agent-runtimes \
  --query 'agentRuntimes[].{id:agentRuntimeId, status:status}'

# 查看 Runtime 详情
RUNTIME_ARN=$(aws ssm get-parameter --name /app/customersupport/agentcore/runtime_viz_arn --query 'Parameter.Value' --output text)

echo "Runtime ARN: $RUNTIME_ARN"
```

Runtime 状态应该为 `ACTIVE`。

---

## ✅ 检查清单

- [ ] 理解 Runtime 的部署流程（代码 → CodeBuild → ECR → Runtime）
- [ ] 理解 Agent 的完整调用链路
- [ ] 理解本地工具和 Gateway 工具的区别
- [ ] Runtime 部署成功，状态为 ACTIVE
- [ ] 理解 Runtime API 的请求和响应格式

---

[⬅️ 上一模块: Policy Engine](./module-04-policy.md) | [下一模块: 前端可视化 ➡️](./module-06-frontend.md)
