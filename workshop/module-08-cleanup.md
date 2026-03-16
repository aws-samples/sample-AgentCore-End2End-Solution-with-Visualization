# 模块 8: 清理资源

> ⏱️ 预计时间：10 分钟

## 学习目标

- 清理所有 AgentCore 资源
- 清理 CloudFormation 基础设施栈
- 确认所有资源已删除

---

## 8.1 清理说明

> ⚠️ **AWS Event 参与者**：如果您使用的是 Workshop Studio 提供的临时账号，活动结束后账号会被自动清理，您可以跳过本模块。但建议仍然执行清理操作作为练习。

> ⚠️ **使用自有账号的参与者**：请务必完成本模块的所有步骤，避免持续产生费用。

---

## 8.2 步骤 1：清理 AgentCore 资源

运行清理脚本：

```bash
python cleanup.py
```

脚本会提示确认，然后依次删除：

1. **前端资源** - CloudFront 分发 + S3 Bucket
2. **AgentCore Runtime** - 容器化的 Agent 运行环境
3. **AgentCore Gateway** - MCP 工具路由（含所有 Target）
4. **Policy Engine** - Cedar 策略规则
5. **CouponTool Lambda** - 代金券批复函数
6. **AgentCore Memory** - 记忆存储

> ⏳ CloudFront 分发删除可能需要 5-10 分钟（需要先禁用再删除）。

### 验证 AgentCore 资源已删除

```bash
# 检查 Runtime
aws bedrock-agentcore-control list-agent-runtimes \
  --query 'agentRuntimes[?contains(agentRuntimeId, `customer_support`)].{id:agentRuntimeId, status:status}'

# 检查 Gateway
aws bedrock-agentcore-control list-gateways \
  --query 'items[?contains(name, `customersupport`)].{name:name, status:status}'

# 检查 Memory
aws bedrock-agentcore-control list-memories \
  --query 'memories[?contains(name, `CustomerSupport`)].{name:name, status:status}'
```

以上命令应该返回空结果或显示资源正在删除中。

---

## 8.3 步骤 2：清理 CloudFormation 栈

```bash
# 删除基础设施栈（DynamoDB、Lambda、IAM Roles）
aws cloudformation delete-stack --stack-name CustomerSupportStackInfra

# 删除 Cognito 栈（User Pool、Clients）
aws cloudformation delete-stack --stack-name CustomerSupportStackCognito
```

### 等待删除完成

```bash
# 等待 Infrastructure 栈删除
aws cloudformation wait stack-delete-complete --stack-name CustomerSupportStackInfra
echo "Infrastructure stack deleted"

# 等待 Cognito 栈删除
aws cloudformation wait stack-delete-complete --stack-name CustomerSupportStackCognito
echo "Cognito stack deleted"
```

> ⏳ 栈删除大约需要 3-5 分钟。

---

## 8.4 步骤 3：清理 S3 Bucket（prereq.sh 创建的）

```bash
# 获取 bucket 名称
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
BUCKET_NAME="customersupport112-${ACCOUNT_ID}-${REGION}"

# 清空并删除 bucket
aws s3 rb s3://${BUCKET_NAME} --force
```

---

## 8.5 步骤 4：清理本地文件

```bash
# 删除部署信息文件
rm -f deployment_info.yaml

# 删除 AgentCore 配置文件
rm -f .bedrock_agentcore.yaml Dockerfile .dockerignore

# 删除前端构建产物
rm -rf frontend/dist frontend/node_modules

# 删除前端环境变量
rm -f frontend/.env

# 删除 Lambda ZIP 包
rm -f lambda.zip
```

---

## 8.6 验证清理完成

### 检查 CloudFormation 栈

```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `CustomerSupport`)].StackName'
```

应该返回空列表 `[]`。

### 检查 ECR 仓库

```bash
aws ecr describe-repositories \
  --query 'repositories[?contains(repositoryName, `bedrock-agentcore`)].repositoryName'
```

如果仍有残留仓库，手动删除：

```bash
aws ecr delete-repository --repository-name <repository-name> --force
```

---

## 8.7 资源清理清单

| 资源 | 清理方式 | 状态 |
|------|----------|------|
| AgentCore Runtime | `cleanup.py` | ☐ |
| AgentCore Gateway | `cleanup.py` | ☐ |
| AgentCore Memory | `cleanup.py` | ☐ |
| Policy Engine | `cleanup.py` | ☐ |
| CouponTool Lambda | `cleanup.py` | ☐ |
| CloudFront 分发 | `cleanup.py` | ☐ |
| 前端 S3 Bucket | `cleanup.py` | ☐ |
| Infrastructure Stack | `aws cloudformation delete-stack` | ☐ |
| Cognito Stack | `aws cloudformation delete-stack` | ☐ |
| prereq S3 Bucket | `aws s3 rb --force` | ☐ |
| ECR 仓库 | 手动检查 | ☐ |
| 本地文件 | `rm` 命令 | ☐ |

---

## 🎉 Workshop 完成

恭喜您完成了 Amazon Bedrock AgentCore 端到端实战 Workshop！

### 您学到了什么

在这个 Workshop 中，您从零开始构建了一个完整的 AI 客服系统，实践了以下 AgentCore 核心能力：

- **AgentCore Runtime** - 将 Agent 代码容器化部署为生产级服务
- **AgentCore Gateway** - 使用 MCP 协议统一管理工具调用
- **AgentCore Memory** - 让 Agent 跨会话记住用户偏好和对话事实
- **AgentCore Policy Engine** - 使用 Cedar 策略语言实现条件化访问控制
- **Cognito 集成** - 实现 M2M 和用户认证的双 Client 架构
- **前端可视化** - 实时展示 Agent 工作流的执行过程

### 进一步学习

- [Amazon Bedrock AgentCore 文档](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Strands Agents SDK](https://github.com/strands-agents/strands-agents-sdk-python)
- [Cedar 策略语言](https://www.cedarpolicy.com/)
- [MCP 协议](https://modelcontextprotocol.io/)

---

[⬅️ 上一模块: 端到端测试](./module-07-testing.md) | [返回目录 📚](./README.md)
