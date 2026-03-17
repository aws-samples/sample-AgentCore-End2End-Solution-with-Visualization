# 模块 1: 基础设施部署

> ⏱️ 预计时间：15 分钟

## 学习目标

- 理解系统的整体架构
- 使用 CloudFormation 部署 DynamoDB、Lambda、Cognito 等基础资源
- 验证基础资源创建成功

---

## 1.1 整体方案架构

在开始动手之前，先来看一下我们要构建的完整系统架构：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户浏览器                                     │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    React 前端 (Cloudscape UI)                        │   │
│  │  ┌────────────┐  ┌─────────────────────┐  ┌──────────────────────┐  │   │
│  │  │ 登录页面    │  │ 聊天界面             │  │ 工作流可视化          │  │   │
│  │  │ (Cognito)  │  │ (Agent 对话)         │  │ (React Flow)        │  │   │
│  │  └────────────┘  └─────────────────────┘  └──────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ HTTPS (Bearer JWT)
                          ┌────────▼────────┐
                          │   CloudFront     │
                          │   (CDN + SPA)    │
                          └────────┬─────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────────┐
│  AWS Cloud                       │                                          │
│                                  │                                          │
│  ┌───────────────────────────────▼───────────────────────────────────────┐  │
│  │                    Amazon Bedrock AgentCore                           │  │
│  │                                                                       │  │
│  │  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────────┐  │  │
│  │  │   Runtime    │───▶│  Strands     │───▶│    AgentCore Memory     │  │  │
│  │  │  (容器化     │    │  Agent       │    │  ┌───────────────────┐  │  │  │
│  │  │   部署)      │    │  (Claude     │    │  │ User Preference   │  │  │  │
│  │  │             │    │   Haiku 4.5) │    │  │ Semantic          │  │  │  │
│  │  └─────────────┘    └──────┬───────┘    │  └───────────────────┘  │  │  │
│  │                            │             └─────────────────────────┘  │  │
│  │                    ┌───────▼────────┐                                 │  │
│  │                    │   AgentCore    │    ┌─────────────────────────┐  │  │
│  │                    │   Gateway      │───▶│  AgentCore Policy      │  │  │
│  │                    │   (MCP 协议)   │    │  Engine (Cedar 规则)   │  │  │
│  │                    └───┬────┬────┬──┘    │                         │  │  │
│  │                        │    │    │       │  ✅ amount < 500 允许   │  │  │
│  │                        │    │    │       │  ❌ amount ≥ 500 拒绝   │  │  │
│  │                        │    │    │       └─────────────────────────┘  │  │
│  └────────────────────────┼────┼────┼───────────────────────────────────┘  │
│                           │    │    │                                       │
│  ┌────────────────────────▼────▼────▼───────────────────────────────────┐  │
│  │                      AWS Lambda 工具                                  │  │
│  │                                                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │  │
│  │  │ check_       │  │ web_search   │  │ CouponTool   │               │  │
│  │  │ warranty_    │  │ (DuckDuckGo) │  │ (代金券批复)  │               │  │
│  │  │ status       │  │              │  │              │               │  │
│  │  └──────┬───────┘  └──────────────┘  └──────────────┘               │  │
│  │         │                                                             │  │
│  │  ┌──────▼───────┐                                                     │  │
│  │  │  DynamoDB    │                                                     │  │
│  │  │  (Warranty + │                                                     │  │
│  │  │   Customer)  │                                                     │  │
│  │  └──────────────┘                                                     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐   │
│  │  Cognito          │  │  SSM Parameter    │  │  CloudWatch           │   │
│  │  User Pool        │  │  Store            │  │  (Observability)      │   │
│  │  ┌─────────────┐  │  │  (配置管理)        │  │  (日志 + X-Ray 追踪)  │   │
│  │  │Machine Client│  │  └───────────────────┘  └───────────────────────┘   │
│  │  │Web Client   │  │                                                     │
│  │  └─────────────┘  │                                                     │
│  └───────────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 数据流说明

| 步骤 | 流程 | 说明 |
|------|------|------|
| ① | 用户 → CloudFront → 前端 | 用户通过浏览器访问 React 前端 |
| ② | 前端 → Cognito | 用户登录，获取 JWT Token |
| ③ | 前端 → Runtime | 发送对话请求（携带 JWT） |
| ④ | Runtime → Agent | Agent 分析用户意图，决定调用哪些工具 |
| ⑤ | Agent → Memory | 检索用户历史偏好和对话记忆 |
| ⑥ | Agent → Gateway | 通过 MCP 协议调用远程工具 |
| ⑦ | Gateway → Policy Engine | 评估 Cedar 策略（如代金券金额限制） |
| ⑧ | Gateway → Lambda | Policy 允许后，调用对应的 Lambda 工具 |
| ⑨ | Lambda → DynamoDB | 查询保修数据等 |
| ⑩ | 响应原路返回 | 结果 + trace events → 前端工作流可视化 |

### 部署分两步

本 Workshop 的部署分为两个阶段：

| 阶段 | 脚本 | 创建的资源 |
|------|------|-----------|
| **阶段 1**（本模块） | `bash prereq.sh` | DynamoDB、Lambda、Cognito、IAM Roles、SSM Parameters |
| **阶段 2**（模块 2-6） | `python deploy.py` | Memory、Gateway、Policy Engine、Runtime、前端 |

---

## 1.2 基础设施详解

在部署 AgentCore 组件之前，我们需要先创建以下基础资源：

| 资源 | 用途 |
|------|------|
| DynamoDB 表（Warranty） | 存储产品保修信息 |
| DynamoDB 表（Customer） | 存储客户档案 |
| Lambda 函数 | 提供保修查询和网页搜索工具 |
| Cognito User Pool | 用户认证（Machine Client + Web Client） |
| IAM Roles | Runtime Role、Gateway Role |
| SSM Parameters | 存储配置信息 |
| S3 Bucket | 存储 Lambda 代码 |

### CloudFormation 栈结构

```
CloudFormation Stack: CustomerSupportStackInfra
├── DynamoDB: Warranty Table（含测试数据）
├── DynamoDB: Customer Profile Table（含测试数据）
├── Lambda: CustomerSupportLambda（warranty + web search）
├── IAM: RuntimeAgentCoreRole
├── IAM: GatewayAgentCoreRole
└── SSM Parameters（各种配置）

CloudFormation Stack: CustomerSupportStackCognito
├── Cognito User Pool
├── Machine Client（用于 Gateway M2M 认证）
├── Web Client（用于前端用户登录）
├── Resource Server（OAuth2 scope）
└── SSM Parameters（认证配置）
```

---

## 1.3 理解 CloudFormation 模板

### 基础设施模板 (`prerequisite/infrastructure.yaml`)

这个模板创建了核心的数据和计算资源：

**IAM Roles：**
- `RuntimeAgentCoreRole` - AgentCore Runtime 使用的角色，包含 Bedrock 模型调用、ECR 镜像拉取、CloudWatch 日志、Memory 访问等权限
- `GatewayAgentCoreRole` - AgentCore Gateway 使用的角色，包含 Lambda 调用权限

**DynamoDB 表：**
- Warranty 表 - 以 `serial_number` 为主键，包含 `customer_id` 的 GSI
- Customer Profile 表 - 以 `customer_id` 为主键，包含 email 和 phone 的 GSI

**Lambda 函数：**
- `CustomerSupportLambda` - 提供 `check_warranty_status` 和 `web_search` 两个工具

### Cognito 模板 (`prerequisite/cognito.yaml`)

这个模板创建了认证相关资源：

**两个 App Client：**
- `MachineUserPoolClient` - 使用 `client_credentials` 流程，用于 Runtime 调用 Gateway
- `WebUserPoolClient` - 使用 `code` 流程 + `USER_PASSWORD_AUTH`，用于前端用户登录

> 💡 **为什么需要两个 Client？**
> - Machine Client：Runtime 作为服务端需要以自己的身份调用 Gateway（M2M 认证）
> - Web Client：前端用户需要用用户名密码登录，获取 token 后直接调用 Runtime

---

## 1.4 部署基础设施

运行 `prereq.sh` 脚本：

```bash
# 重要：先显式设置 Region，确保与 AWS CLI 配置一致
export AWS_REGION=$(aws configure get region)
echo "Using region: $AWS_REGION"

bash prereq.sh
```

> ⚠️ **Region 注意事项**：`prereq.sh` 会优先使用 `AWS_REGION` 环境变量。如果该变量未设置，会尝试从 `aws configure get region` 获取。为避免 Region 不一致导致的问题，建议在运行前用上面的命令显式设置 `AWS_REGION`。

这个脚本会自动完成以下步骤：

1. **创建 S3 Bucket** - 用于存储 Lambda 代码包
2. **打包 Lambda 代码** - 将 `prerequisite/lambda/python/` 目录打包为 ZIP
3. **上传到 S3** - 上传 Lambda 代码包和 DDGS Layer
4. **部署 Infrastructure Stack** - 创建 DynamoDB、Lambda、IAM Roles
5. **部署 Cognito Stack** - 创建 User Pool 和 App Clients

> ⏳ 部署大约需要 5-10 分钟。

### 观察部署过程

脚本运行时，您会看到类似输出：

```
Region: us-east-1
Account ID: 123456789012
🪣 Using S3 bucket: customersupport112-123456789012-us-east-1
📦 Zipping contents of prerequisite/lambda/python into lambda.zip...
☁️ Uploading lambda.zip to s3://...
🚀 Deploying CloudFormation stack: CustomerSupportStackInfra
✅ Stack CustomerSupportStackInfra deployed successfully.
🚀 Deploying CloudFormation stack: CustomerSupportStackCognito
✅ Stack CustomerSupportStackCognito deployed successfully.
✅ Deployment complete.
```

---

## 1.5 验证部署结果

### 检查 CloudFormation 栈状态

```bash
# 检查 Infrastructure 栈
aws cloudformation describe-stacks \
  --stack-name CustomerSupportStackInfra \
  --query 'Stacks[0].StackStatus'

# 检查 Cognito 栈
aws cloudformation describe-stacks \
  --stack-name CustomerSupportStackCognito \
  --query 'Stacks[0].StackStatus'
```

两个栈都应该显示 `"CREATE_COMPLETE"`。

### 检查 SSM 参数

```bash
# 查看所有创建的参数
aws ssm get-parameters-by-path \
  --path "/app/customersupport" \
  --recursive \
  --query 'Parameters[].Name'
```

您应该看到以下参数：
```json
[
    "/app/customersupport/agentcore/client_id",
    "/app/customersupport/agentcore/web_client_id",
    "/app/customersupport/agentcore/pool_id",
    "/app/customersupport/agentcore/cognito_discovery_url",
    "/app/customersupport/agentcore/cognito_token_url",
    "/app/customersupport/agentcore/gateway_iam_role",
    "/app/customersupport/agentcore/runtime_iam_role",
    "/app/customersupport/agentcore/lambda_arn",
    ...
]
```

### 检查 DynamoDB 测试数据

```bash
# 查看保修数据
aws dynamodb scan \
  --table-name $(aws ssm get-parameter --name /app/customersupport/dynamodb/warranty_table_name --query 'Parameter.Value' --output text) \
  --select COUNT
```

应该显示 8 条保修记录。

### 测试 Lambda 函数

```bash
# 获取 Lambda 函数名
LAMBDA_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name CustomerSupportStackInfra \
  --query 'StackResources[?ResourceType==`AWS::Lambda::Function` && starts_with(LogicalResourceId, `CustomerSupport`)].PhysicalResourceId' \
  --output text)

# 测试保修查询
aws lambda invoke \
  --function-name $LAMBDA_NAME \
  --payload '{"tool_name": "check_warranty_status", "parameters": {"serial_number": "ABC12345678"}}' \
  /tmp/lambda-output.json

cat /tmp/lambda-output.json
```

---

## 1.6 深入理解：Cognito 双 Client 架构

这是本系统的一个关键设计点 — 使用两个不同的 Cognito App Client 分别服务前端用户和后端服务。

### 架构图

```
                    ┌─────────────────┐
                    │  Cognito User   │
                    │     Pool        │
                    └────┬───────┬────┘
                         │       │
              ┌──────────▼─┐  ┌──▼──────────┐
              │  Machine   │  │    Web      │
              │  Client    │  │   Client    │
              │(有 Secret) │  │(无 Secret)  │
              └──────┬─────┘  └──────┬──────┘
                     │               │
              client_credentials   USER_PASSWORD_AUTH
                     │               │
              ┌──────▼─────┐  ┌──────▼──────┐
              │  Runtime   │  │   前端      │
              │  → Gateway │  │  → Runtime  │
              └────────────┘  └─────────────┘
```

### Web Client：前端用户登录

> 📁 **创建位置**：`prerequisite/cognito.yaml` → `WebUserPoolClient`
> 📁 **使用位置**：`frontend/src/services/authService.ts`

Web Client 没有 Secret（`GenerateSecret: false`），适合在浏览器端使用。前端通过 `USER_PASSWORD_AUTH` 流程让用户输入用户名密码登录：

```typescript
// frontend/src/services/authService.ts
const response = await fetch(endpoint, {
  body: JSON.stringify({
    AuthFlow: 'USER_PASSWORD_AUTH',
    ClientId: this.config.clientId,  // ← Web Client ID
    AuthParameters: { USERNAME: username, PASSWORD: password },
  }),
})
```

登录成功后，前端拿到 Access Token，用它直接调用 AgentCore Runtime API：

```typescript
// frontend/src/services/agentService.ts
const response = await axios.post(endpoint, { prompt }, {
  headers: { 'Authorization': `Bearer ${authToken}` },  // ← Web Client 的 token
})
```

### Machine Client：Runtime 调用 Gateway

> 📁 **创建位置**：`prerequisite/cognito.yaml` → `MachineUserPoolClient`
> 📁 **使用位置**：`agent/customer_support_agent.py` → `invoke` 函数

Machine Client 有 Secret（`GenerateSecret: true`），使用 OAuth2 `client_credentials` 流程获取 M2M（Machine-to-Machine）token。Runtime 收到前端请求后，不会把用户的 token 转发给 Gateway，而是用自己的 Machine Client 身份去调用：

```python
# agent/customer_support_agent.py → invoke 函数
# 1. 从 SSM 获取 Machine Client 配置
machine_client_id = ssm.get_parameter(Name="/app/customersupport/agentcore/client_id")
machine_client_secret = ssm.get_parameter(Name="/app/customersupport/agentcore/client_secret")

# 2. OAuth2 client_credentials 流程获取 M2M token
credentials = base64.b64encode(f"{machine_client_id}:{machine_client_secret}".encode()).decode()
token_response = httpx.post(token_url, headers={
    "Authorization": f"Basic {credentials}"
}, data={
    "grant_type": "client_credentials",
    "scope": auth_scope
})
machine_token = token_response.json()["access_token"]

# 3. 用 Machine token 调用 Gateway
mcp_client = MCPClient(lambda: streamablehttp_client(
    url=gateway_url,
    headers={"Authorization": f"Bearer {machine_token}"}  # ← Machine Client 的 token
))
```

### 完整认证链路

```
用户浏览器                    AWS Cloud
┌──────────┐                 ┌──────────────────────────────────────┐
│ 输入密码  │ ──Web Client──▶│ Cognito: USER_PASSWORD_AUTH          │
│          │ ◀──token────── │ → 返回 Access Token                  │
│          │                 └──────────────────────────────────────┘
│          │                 ┌──────────────────────────────────────┐
│ 发送对话  │ ──token──────▶ │ AgentCore Runtime                    │
│          │                 │   ↓ 收到用户请求                     │
│          │                 │   ↓ 用 Machine Client credentials    │
│          │                 │   ↓ 获取 M2M token                   │
│          │                 │   ↓ 用 M2M token 调用 Gateway        │
│          │                 │ AgentCore Gateway                    │
│          │                 │   ↓ 验证 M2M token                   │
│          │                 │   ↓ Policy Engine 评估               │
│          │                 │   ↓ 调用 Lambda 工具                 │
│          │ ◀──响应──────── │ → 返回结果                           │
└──────────┘                 └──────────────────────────────────────┘
```

### 为什么不直接用用户 token 调 Gateway？

- **安全隔离**：用户 token 只到 Runtime 层，不暴露给下游服务
- **权限分离**：Machine Client 可以有不同于用户的权限范围（scope）
- **M2M 标准模式**：服务间调用使用 `client_credentials` 是 OAuth2 的标准实践

---

## ✅ 检查清单

- [ ] `prereq.sh` 执行成功
- [ ] 两个 CloudFormation 栈状态为 `CREATE_COMPLETE`
- [ ] SSM 参数已创建
- [ ] DynamoDB 表包含测试数据
- [ ] Lambda 函数可以正常调用

---

## 🔧 常见问题

### HeadBucket 404 错误

```
An error occurred (404) when calling the HeadBucket operation: Not Found
```

原因：`AWS_REGION` 环境变量与 AWS CLI 配置的 Region 不一致，导致 S3 Bucket 创建在了一个 Region，但验证时用了另一个 Region。

解决：在运行 `prereq.sh` 前确保 Region 一致：
```bash
export AWS_REGION=$(aws configure get region)
bash prereq.sh
```

### CloudFormation 栈创建失败

```
Failed to create/update the stack
```

查看具体失败原因：
```bash
aws cloudformation describe-stack-events \
  --stack-name CustomerSupportStackInfra \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

常见原因：
- **IAM 权限不足**：账号缺少 `iam:CreateRole` 权限。Workshop Studio 账号需要确保 IAM policy 包含完整的 IAM 操作权限
- **SSM 参数冲突**：之前的部署残留。先删除旧栈再重建：
  ```bash
  aws cloudformation delete-stack --stack-name CustomerSupportStackInfra
  aws cloudformation wait stack-delete-complete --stack-name CustomerSupportStackInfra
  bash prereq.sh
  ```

### pip install 报错 "No matching distribution"

```
ERROR: No matching distribution found for bedrock-agentcore-sdk-python
```

原因：旧版 `requirements.txt` 中的包名有误。确保使用 workshop 分支的最新代码：
```bash
git checkout workshop
pip3 install -r requirements.txt
```

---

[⬅️ 上一模块: 环境准备](./module-00-prerequisites.md) | [下一模块: AgentCore Memory ➡️](./module-02-memory.md)
