# 模块 0: 环境准备

> ⏱️ 预计时间：15 分钟

## 学习目标

- 获取 AWS 账号访问权限
- 安装必要的开发工具
- 启用 Bedrock 模型访问
- 克隆项目代码

---

## 0.1 Preparation（获取 AWS 账号）

本 Workshop 支持两种方式获取 AWS 账号。请根据您的情况选择对应的方式。

---

### 方式一：参加 AWS 活动（AWS Event）

> 如果您正在参加由 AWS 组织的活动（如 re:Invent、Summit、Immersion Day 等），请按照以下步骤操作。**请跳过"方式二"。**

#### 步骤 1：访问 Workshop Studio

1. 打开浏览器，访问 [https://catalog.workshops.aws/join](https://catalog.workshops.aws/join)
2. 使用推荐的认证方式登录（Email one-time password 或 Amazon 账号）

#### 步骤 2：输入活动访问码

1. 输入讲师提供的 **Event Access Code**（12 位活动访问码）
2. 点击 **Next**

![Event Access Code](https://static.us-east-1.prod.workshops.aws/public/44c91d5b-99f5-4d32-8a3e-1e054e3be85e/static/images/preparation/event-access-code.png)

#### 步骤 3：接受条款并加入

1. 阅读条款和条件
2. 勾选 **I agree with the Terms and Conditions**
3. 点击 **Join event**

#### 步骤 4：获取 AWS 凭证

加入活动后，您会看到活动仪表板页面：

1. 点击左下角的 **Open AWS Console** 打开 AWS 管理控制台
2. 点击左下角的 **Get AWS CLI Credentials** 获取 CLI 凭证

将显示的凭证复制到您的终端中：

```bash
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."
export AWS_DEFAULT_REGION=us-east-1
```

#### 步骤 5：验证凭证

```bash
aws sts get-caller-identity
```

您应该看到类似输出：
```json
{
    "UserId": "AROA...:MasterKey",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/WSParticipantRole/..."
}
```

> ⚠️ **注意**：Workshop Studio 提供的临时账号有时间限制，请在活动期间完成所有实验。活动结束后账号将被自动清理。

---

### 方式二：使用自己的 AWS 账号

> 如果您不是在 AWS 活动中进行本 Workshop，请按照以下步骤使用自己的 AWS 账号。**请跳过"方式一"。**

#### AWS 账号权限要求

您的 IAM 用户或角色需要具备以下服务的权限：

| 服务 | 所需权限 |
|------|----------|
| IAM | 创建 Role 和 Policy |
| CloudFormation | 创建和管理 Stack |
| Lambda | 创建和调用函数 |
| DynamoDB | 创建表和读写数据 |
| S3 | 创建 Bucket 和上传文件 |
| CloudFront | 创建分发 |
| Cognito | 创建 User Pool |
| Bedrock | 调用模型 |
| Bedrock AgentCore | 创建 Runtime、Gateway、Memory、Policy Engine |
| SSM Parameter Store | 读写参数 |
| ECR | 创建仓库和推送镜像 |
| CloudWatch | 查看日志和监控 |
| CodeBuild | 构建容器镜像 |

> 💡 **建议**：如果您有 AdministratorAccess 权限，可以跳过权限检查。

#### 配置 AWS CLI

```bash
# 检查 AWS CLI 版本（需要 v2）
aws --version

# 配置凭证（如果尚未配置）
aws configure

# 确认身份
aws sts get-caller-identity
```

#### 设置 Region

```bash
# 推荐使用 us-east-1
export AWS_REGION=us-east-1
aws configure set region us-east-1
```

> ⚠️ **费用提醒**：本 Workshop 会创建 AWS 资源并产生费用。请在完成后按照 [模块 8: 清理资源](./module-08-cleanup.md) 删除所有资源，避免持续产生费用。

---

## 0.2 安装开发工具

无论您使用哪种方式获取 AWS 账号，都需要在本地安装以下工具。

### Python 3.10+

```bash
python3 --version
# 应该显示 Python 3.10 或更高版本
```

如果未安装，请参考：
- macOS: `brew install python@3.12`
- Linux: `sudo apt install python3.12` 或 `sudo yum install python3.12`
- Windows: 从 [python.org](https://www.python.org/downloads/) 下载安装

### Node.js 18+

```bash
node --version
# 应该显示 v18 或更高版本

npm --version
```

如果未安装，请参考：
- macOS: `brew install node`
- 或使用 [nvm](https://github.com/nvm-sh/nvm): `nvm install 18`

---

## 0.3 启用 Bedrock 模型

> 💡 如果您使用 AWS Event 提供的账号，模型可能已经预先启用。请先检查再操作。

在 AWS Console 中启用所需的 Bedrock 模型：

1. 打开 [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock)
2. 确认 Region 为 **us-east-1**（或您选择的 Region）
3. 在左侧导航栏选择 **Model access**
4. 点击 **Manage model access**
5. 勾选以下模型：
   - ✅ **Anthropic Claude Haiku 4.5**（用于 Agent 推理，代码中使用 cross-region 推理 `global.anthropic.claude-haiku-4-5-20251001-v1:0`）
   - ✅ **Amazon Titan Text Embeddings V2**（用于 Knowledge Base 向量化）
6. 点击 **Save changes**

> ⏳ 模型启用可能需要几分钟时间。

> 📁 **模型配置位置**：`agent/customer_support_agent.py` 第 34 行
> ```python
> MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
> ```
> 使用 `global.` 前缀表示 cross-region inference，Bedrock 会自动路由到最近的可用 Region。

验证模型是否可用：

```bash
aws bedrock list-foundation-models \
  --query 'modelSummaries[?contains(modelId, `claude-haiku-4-5`) || contains(modelId, `titan-embed`)].modelId' \
  --output table
```

---

## 0.4 克隆项目代码

```bash
git clone <repository-url>
cd agentcore-sample-with-visualization
```

### 安装 Python 依赖

```bash
pip install -r requirements.txt
```

这会安装以下核心依赖：

| 包名 | 用途 |
|------|------|
| `boto3` | AWS SDK for Python |
| `pyyaml` | 配置文件解析 |
| `rich` | 终端美化输出 |
| `bedrock-agentcore-sdk-python` | AgentCore SDK |
| `bedrock-agentcore-starter-toolkit` | AgentCore 部署工具 |
| `strands-agents` | Strands Agent 框架 |

---

## 0.5 项目结构概览

```
agentcore-sample-with-visualization/
├── prereq.sh                      # 基础资源创建脚本
├── deploy.py                      # AgentCore 资源部署脚本（全自动）
├── cleanup.py                     # 资源清理脚本
├── config.yaml                    # 配置文件
├── agent/                         # Agent 代码
│   ├── customer_support_agent.py  # 主 Agent 逻辑
│   ├── tools.py                   # 本地工具定义
│   └── requirements.txt           # Agent 运行时依赖
├── lambda/                        # Lambda 函数代码
│   ├── lambda_function.py         # 主 Lambda（warranty + web search）
│   ├── check_warranty.py          # 保修查询逻辑
│   ├── web_search.py              # 网页搜索逻辑
│   ├── lambda_coupon.py           # 代金券工具
│   ├── api_spec.json              # 工具 API 规范
│   └── api_spec_coupon.json       # 代金券 API 规范
├── frontend/                      # React 前端
│   └── src/
│       ├── components/            # UI 组件（Chat、Workflow、Login）
│       ├── services/              # API 服务（auth、agent）
│       └── config/                # 工作流图配置
├── prerequisite/                  # CloudFormation 模板
│   ├── infrastructure.yaml        # 基础设施（DynamoDB、Lambda、IAM）
│   └── cognito.yaml               # Cognito（User Pool、Clients）
├── knowledge_base_data/           # Knowledge Base 文档
├── utils/                         # 辅助工具
│   ├── agentcore_helper.py        # AgentCore 资源操作
│   └── aws_helper.py              # AWS 资源操作（S3、CloudFront）
└── workshop/                      # Workshop 文档（您正在阅读的）
```

---

## 0.6 理解配置文件

打开 `config.yaml`，了解关键配置项：

```yaml
# 项目配置
project:
  name: agentcore-demo

# Cognito 认证
cognito:
  test_user:
    username: testuser
    password: MyPassword123!

# AgentCore Memory
memory:
  name: CustomerSupportMemory

# AgentCore Gateway
gateway:
  name: customersupport-gw

# AgentCore Runtime
runtime:
  agent_name: customer_support_agent
  entrypoint: agent/customer_support_agent.py

# Policy Engine
policy:
  engine_name: CustomerSupport_PolicyEngine
  mode: ENFORCE          # ENFORCE = 实际执行; LOG_ONLY = 仅记录
  coupon_limit: 500      # 代金券金额限制（美元）

# 前端部署
frontend:
  deploy_to_s3: true     # true = 部署到 CloudFront
```

---

## ✅ 检查清单

在继续下一模块之前，请确认：

- [ ] 已获取 AWS 账号访问权限（Event Studio 或自有账号）
- [ ] `aws sts get-caller-identity` 能正常返回
- [ ] Region 已设置（推荐 `us-east-1`）
- [ ] Python 3.10+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] Python 依赖已安装（`pip install -r requirements.txt`）
- [ ] Bedrock 模型已启用（Claude Haiku 4.5 + Titan Embeddings V2）
- [ ] 项目代码已克隆

---

[⬅️ 返回目录](./README.md) | [下一模块: 基础设施部署 ➡️](./module-01-infrastructure.md)
