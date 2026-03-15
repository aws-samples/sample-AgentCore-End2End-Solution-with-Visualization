# 模块 3: AgentCore Gateway

> ⏱️ 预计时间：20 分钟

## 学习目标

- 理解 AgentCore Gateway 的作用和 MCP 协议
- 创建 Gateway 并配置 Lambda Target
- 部署 CouponTool Lambda 并添加为 Gateway Target
- 理解 Gateway 的认证机制

---

## 3.1 什么是 AgentCore Gateway？

AgentCore Gateway 是一个托管的工具路由服务，它使用 **MCP（Model Context Protocol）** 协议，让 Agent 能够安全地调用各种外部工具。

### 为什么需要 Gateway？

直接调用工具的问题：
- ❌ Agent 需要知道每个工具的调用方式
- ❌ 没有统一的认证和授权
- ❌ 无法集中管理工具访问策略
- ❌ 难以添加新工具

使用 Gateway 的优势：
- ✅ 统一的 MCP 协议接口
- ✅ 集中的认证（Cognito JWT）
- ✅ 可以关联 Policy Engine 进行访问控制
- ✅ 支持多个 Target（Lambda、HTTP 等）
- ✅ 工具发现和路由自动化

### 架构

```
                    ┌──────────────┐
                    │    Agent     │
                    │  (MCP Client)│
                    └──────┬──────┘
                           │ MCP Protocol
                    ┌──────▼──────┐
                    │   Gateway   │ ← JWT 认证
                    │  (MCP Server)│ ← Policy 检查
                    └──┬───┬───┬──┘
                       │   │   │
              ┌────────▼┐ ┌▼────┐ ┌▼────────┐
              │LambdaTools│ │Coupon│ │ 更多...  │
              │  Target  │ │Target│ │ Target  │
              └──────────┘ └──────┘ └─────────┘
```

---

## 3.2 Gateway 的组成

### Target（工具目标）

每个 Target 代表一组工具的提供者：

| Target | 工具 | 说明 |
|--------|------|------|
| LambdaTools | `check_warranty_status`, `web_search` | 保修查询和网页搜索 |
| CouponToolTarget | `CouponTool` | 代金券批复 |

### 认证配置

Gateway 使用 **Custom JWT Authorizer**，配置了两个 allowed clients：

```python
authorizerConfiguration={
    "customJWTAuthorizer": {
        "allowedClients": [
            machine_client_id,  # Runtime 的 M2M token
            web_client_id,      # 前端用户的 token
        ],
        "discoveryUrl": discovery_url,  # Cognito OIDC 发现 URL
    }
}
```

---

## 3.3 创建 Gateway

### 代码解析

查看 `utils/agentcore_helper.py` 中的 `create_agentcore_gateway` 函数：

```python
def create_agentcore_gateway(name, description, role_arn, client_id, 
                              discovery_url, lambda_arn, api_spec_file, 
                              region, web_client_id=None):
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # 准备 allowed clients 列表
    allowed_clients = [client_id]  # Machine Client
    if web_client_id:
        allowed_clients.append(web_client_id)  # Web Client

    # 创建 Gateway
    response = gateway_client.create_gateway(
        name=name,
        roleArn=role_arn,
        protocolType="MCP",           # 使用 MCP 协议
        authorizerType="CUSTOM_JWT",  # JWT 认证
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "allowedClients": allowed_clients,
                "discoveryUrl": discovery_url,
            }
        },
        description=description,
    )
    gateway_id = response["gatewayId"]
```

### 添加 Lambda Target

```python
    # 加载 API 规范
    with open(api_spec_file, "r") as f:
        api_spec = json.load(f)

    # 添加 Lambda Target
    gateway_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="LambdaTools",
        description="Lambda tools for customer support",
        targetConfiguration={
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {"inlinePayload": api_spec},
                }
            }
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    )
```

---

## 3.4 理解工具 API 规范

Gateway 需要知道每个工具的输入输出格式。这通过 API Spec 定义：

### `lambda/api_spec.json`（LambdaTools Target）

```json
[
  {
    "name": "check_warranty_status",
    "description": "Check the warranty status of a product using its serial number",
    "inputSchema": {
      "type": "object",
      "properties": {
        "serial_number": {
          "type": "string",
          "description": "Product serial number"
        },
        "customer_email": {
          "type": "string",
          "description": "Customer email for verification (optional)"
        }
      },
      "required": ["serial_number"]
    }
  },
  {
    "name": "web_search",
    "description": "Search the web for updated information",
    "inputSchema": {
      "type": "object",
      "properties": {
        "keywords": { "type": "string", "description": "Search query" },
        "region": { "type": "string", "description": "Search region" },
        "max_results": { "type": "integer", "description": "Max results" }
      },
      "required": ["keywords"]
    }
  }
]
```

### `lambda/api_spec_coupon.json`（CouponTool Target）

```json
[
  {
    "name": "CouponTool",
    "description": "批复代金券给客户，金额必须小于500美元",
    "inputSchema": {
      "type": "object",
      "properties": {
        "amount": {
          "type": "integer",
          "description": "代金券金额（美元），必须小于500"
        }
      },
      "required": ["amount"]
    }
  }
]
```

---

## 3.5 部署 CouponTool Lambda

CouponTool 是一个独立的 Lambda 函数，用于演示 Policy Engine 的访问控制：

```python
def create_coupon_lambda(lambda_name, role_name, region):
    # 1. 创建 IAM Role
    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=trust_policy,
    )
    
    # 2. 打包 Lambda 代码
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.write("lambda/lambda_coupon.py", "lambda_function.py")
    
    # 3. 创建 Lambda 函数
    lambda_client.create_function(
        FunctionName=lambda_name,
        Runtime="python3.12",
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": zip_buffer.read()},
    )
```

### CouponTool Lambda 代码

```python
# lambda/lambda_coupon.py
def approve_coupon(amount):
    """批复代金券"""
    if amount <= 0:
        return {"success": False, "message": f"❌ 金额必须大于0"}
    
    return {
        "success": True,
        "message": f"✅ 代金券批复成功！金额: ${amount}",
        "coupon_code": f"COUPON-{int(amount * 100)}",
        "amount": amount
    }
```

> 💡 注意：Lambda 本身不做金额限制，金额控制由 Policy Engine 负责（下一模块）。

---

## 3.6 Agent 如何调用 Gateway 工具

在 `agent/customer_support_agent.py` 中，Agent 通过 MCP Client 连接 Gateway：

```python
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# 创建 MCP 客户端
mcp_client = MCPClient(
    lambda: streamablehttp_client(
        url=gateway_url,
        headers={"Authorization": gateway_auth_header}
    )
)

# 创建工具包装函数
@tool
def check_warranty_status(serial_number: str, customer_email: str = None) -> str:
    """Check warranty status via Gateway"""
    result = mcp_client.call_tool_sync(
        tool_use_id=str(uuid.uuid4()),
        name="LambdaTools___check_warranty_status",  # Target名___工具名
        arguments={"serial_number": serial_number}
    )
    return str(result)
```

注意工具名称的格式：`{TargetName}___{ToolName}`，例如：
- `LambdaTools___check_warranty_status`
- `LambdaTools___web_search`
- `CouponToolTarget___CouponTool`

---

## 3.7 验证 Gateway

```bash
# 列出所有 Gateway
aws bedrock-agentcore-control list-gateways \
  --query 'items[].{name:name, id:gatewayId, status:status}'

# 查看 Gateway 详情
GATEWAY_ID=$(aws ssm get-parameter --name /app/customersupport/agentcore/gateway_id --query 'Parameter.Value' --output text)

aws bedrock-agentcore-control get-gateway \
  --gateway-identifier $GATEWAY_ID

# 列出 Gateway Targets
aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier $GATEWAY_ID \
  --query 'items[].{name:name, id:targetId}'
```

---

## ✅ 检查清单

- [ ] 理解 Gateway 的 MCP 协议和路由机制
- [ ] 理解 JWT 认证和 allowed clients 配置
- [ ] 理解工具 API 规范的格式
- [ ] Gateway 创建成功，包含 LambdaTools 和 CouponTool 两个 Target
- [ ] 理解 Agent 如何通过 MCP Client 调用 Gateway 工具

---

[⬅️ 上一模块: AgentCore Memory](./module-02-memory.md) | [下一模块: Policy Engine ➡️](./module-04-policy.md)
