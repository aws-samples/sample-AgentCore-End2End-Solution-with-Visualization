# 模块 1: 基础设施部署

> ⏱️ 预计时间：15 分钟

## 学习目标

- 理解系统的基础设施架构
- 使用 CloudFormation 部署 DynamoDB、Lambda、Cognito 等基础资源
- 验证基础资源创建成功

---

## 1.1 基础设施概览

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

### 架构图

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

## 1.2 理解 CloudFormation 模板

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

## 1.3 部署基础设施

运行 `prereq.sh` 脚本：

```bash
# 重要：先显式设置 Region，避免脚本使用错误的 Region
export AWS_REGION=us-east-1  # 或您选择的 Region

bash prereq.sh
```

> ⚠️ **Region 注意事项**：`prereq.sh` 会优先使用 `AWS_REGION` 环境变量。如果该变量未设置，会尝试从 `aws configure get region` 获取。为避免 Region 不一致导致的问题，建议在运行前显式 `export AWS_REGION`。

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

## 1.4 验证部署结果

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

## 1.5 深入理解：Cognito 双 Client 架构

这是本系统的一个关键设计点：

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

- **Web Client** 没有 Secret，适合浏览器端使用 `USER_PASSWORD_AUTH` 流程
- **Machine Client** 有 Secret，使用 `client_credentials` 流程获取 M2M token
- Runtime 收到前端请求后，使用 Machine Client 的 token 调用 Gateway

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

解决：在运行 `prereq.sh` 前显式设置 Region：
```bash
export AWS_REGION=$(aws configure get region)
bash prereq.sh
```

---

[⬅️ 上一模块: 环境准备](./module-00-prerequisites.md) | [下一模块: AgentCore Memory ➡️](./module-02-memory.md)
