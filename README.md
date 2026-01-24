# AgentCore E2E 可视化演示 - 一键部署方案

## 📋 概述

完整的 Amazon Bedrock AgentCore 端到端演示

### 包含功能
- ✅ AgentCore Memory（用户偏好 + 语义记忆）
- ✅ AgentCore Gateway（工具共享 + MCP协议）
- ✅ AgentCore Policy Engine（代金券金额控制）⭐
- ✅ AgentCore Runtime（生产级部署 + Streaming支持）
- ✅ React前端（实时工作流可视化）
- ✅ Knowledge Base（技术支持文档）
- ✅ Lambda工具（warranty check + web search + coupon）
- ✅ Cognito登录（用户名密码认证）

## 🚀 快速开始

### 前置要求

1. AWS账号，已配置CLI凭证
2. Python 3.10+
3. Node.js 18+
4. 启用Bedrock模型：Anthropic Claude 3.7 Haiku

### 一键部署（完全自动化）✨

```bash
cd agentcore-sample-with-visualization

# 步骤1: 基础资源（5-10分钟）
bash prereq.sh

# 步骤2: AgentCore + 前端（10-15分钟）
python deploy.py

# 完成！
```

deploy.py会自动完成所有配置和修复。

### 🎯 deploy.py自动完成的配置

1. ✅ **检查前置资源** - 验证prereq.sh是否已运行
2. ✅ **配置Web Client** - 启用USER_PASSWORD_AUTH
3. ✅ **创建测试用户** - testuser@example.com（如果不存在）
4. ✅ **添加Runtime权限** - Gateway、Memory、ECR权限
5. ✅ **添加Gateway Policy权限** - bedrock-agentcore:*（提前配置，确保Policy评估成功）
6. ✅ **创建Memory** - 双策略（用户偏好 + 语义）
7. ✅ **创建Gateway** - MCP协议，**创建时就包含Machine + Web Client**
8. ✅ **部署CouponTool Lambda** - 代金券批复工具
9. ✅ **创建Policy Engine** - 4个Cedar规则（金额控制）
10. ✅ **清理失败Policy** - 自动删除并重建失败的规则
11. ✅ **部署Runtime** - 允许Machine + Web Client
12. ✅ **构建前端** - 生成.env，npm build
13. ✅ **部署CloudFront** - S3 + OAI + 缓存失效
14. ✅ **验证Policy** - 检查规则状态，等待IAM权限传播（30秒）
15. ✅ **验证访问** - 自动测试CloudFront是否正常

**关键优化**：
- Gateway创建时就包含所有allowed clients（无需后续update）
- Gateway Role在部署前就添加Policy权限（无需等待权限传播）
- 自动清理失败的Policy规则并重建
- 自动等待IAM权限传播，确保Policy评估成功

### 启动前端

#### 方式1: 本地开发（推荐用于测试）

```bash
cd frontend
npm run dev
```

访问 http://localhost:3000

**优势**: 实时热更新、无需等待CloudFront

#### 方式2: CloudFront部署（推荐用于演示）

修改 `config.yaml`:
```yaml
frontend:
  deploy_to_s3: true
```

然后运行:
```bash
python deploy.py
```

**deploy.py会自动**:
- ✅ 创建/复用CloudFront分发
- ✅ 修复OAI策略不匹配问题
- ✅ 失效缓存
- ✅ 验证访问

访问输出的CloudFront URL（HTTPS）

**注意**: CloudFront首次部署需要5-10分钟生效

### 清理资源

```bash
# 清理AgentCore资源
python cleanup.py

# 清理基础资源
aws cloudformation delete-stack --stack-name CustomerSupportStackInfra
aws cloudformation delete-stack --stack-name CustomerSupportStackCognito
```

## 📁 项目结构

```
agentcore-sample-with-visualization/
├── prereq.sh                      # 基础资源创建脚本
├── deploy.py                      # AgentCore资源部署（完全自动化）
├── cleanup.py                     # 清理脚本
├── config.yaml                    # 配置文件
├── agent/                         # Agent代码（基于lab4_runtime_streaming.py）
├── lambda/                        # Lambda函数
├── frontend/                      # React前端
├── prerequisite/                  # CloudFormation模板
├── knowledge_base_data/           # KB文档
└── utils/                         # 辅助工具
```

## ⚙️ 自动配置功能

**deploy.py会自动检测并修复以下问题**：

1. ✅ **Web Client配置**
   - 检查是否启用USER_PASSWORD_AUTH
   - 如果未启用，自动启用

2. ✅ **测试用户创建**
   - 检查testuser@example.com是否存在
   - 如果不存在，自动创建并设置密码

3. ✅ **Runtime Role权限**
   - 自动添加Gateway权限（GetGateway, InvokeGateway）
   - 自动添加Memory权限（ListEvents, CreateEvent等8个权限）
   - 自动添加ECR权限（修复repository名称不匹配）

4. ✅ **Runtime Authorizer**
   - 自动配置允许Machine Client（用于Gateway）
   - 自动配置允许Web Client（用于前端登录）

5. ✅ **SSM参数**
   - 自动保存Machine Client Secret
   - 自动保存所有必需的配置参数

6. ✅ **CloudFront部署**（新增）
   - 自动创建S3 Bucket + 上传文件
   - 自动创建CloudFront分发 + OAI
   - 自动修复OAI策略不匹配问题
   - 自动失效CloudFront缓存
   - 自动验证访问是否正常

## 🔐 测试账号

- 用户名: testuser@example.com（邮箱格式）
- 密码: MyPassword123!
- Token有效期: 2小时

### 登录方式

前端支持Cognito用户名密码登录：
- 打开CloudFront URL显示登录页面
- 输入用户名密码
- Token自动管理
- 支持退出登录

**CloudFront部署优势**:
- ✅ HTTPS安全访问
- ✅ 全球CDN加速
- ✅ 绕过S3公开访问限制
- ✅ 自动缓存优化
- ✅ SPA路由支持（404重定向）

## 🧪 测试场景

### AWS Console 快速链接

前端UI的header中包含以下AWS Console快速链接，方便查看实际资源：

- **📊 Observability** - CloudWatch GenAI Observability Dashboard
  - 查看所有AgentCore资源的日志和追踪
  - 监控Runtime、Gateway、Memory的运行状态
  - 分析请求链路和性能指标
  
- **🔐 Policy Engine** - AgentCore Policy Engine Console
  - 查看和管理Policy规则（4个Cedar规则）
  - 监控Policy评估结果
  - 调试Policy拒绝原因（如$500代金券被拒）
  
- **📈 Evaluation** - AgentCore Evaluation Console
  - 查看Agent响应质量评估
  - 分析性能指标
  - 优化Agent行为

### 测试场景

### 1. 产品信息查询
```
用户: "What are the specifications for your laptops?"
可视化: User → Runtime → Agent → Tool(Product Info) → Response
```

### 2. 保修检查
```
用户: "Check warranty for serial number ABC12345678"
可视化: User → Runtime → Agent → Gateway → Policy → Tool(Warranty) → Response
```

### 3. 代金券申请（Policy控制）⭐
```
用户: "I need a $100 coupon"
可视化: User → Runtime → Agent → Gateway → Policy(✅ Allow) → Tool(Coupon) → Response

用户: "I need a $500 coupon"
可视化: User → Runtime → Agent → Gateway → Policy(❌ Deny) → Response
```

### 4. 技术支持
```
用户: "How do I install a new CPU?"
可视化: User → Runtime → Agent → Tool(KB) → Response
```

### 5. Web搜索
```
用户: "Search for iPhone 15 troubleshooting"
可视化: User → Runtime → Agent → Gateway → Tool(Web Search) → Response
```

## 🔐 Policy Engine（代金券金额控制）

系统包含Policy Engine，自动控制代金券金额:
- ✅ 金额 < $500: Policy允许，Lambda批复
- ❌ 金额 ≥ $500: Policy拒绝，不调用Lambda

### Policy规则（4个Cedar规则）
1. **AllowCheckWarranty** - 允许保修查询工具
2. **AllowWebSearch** - 允许网页搜索工具
3. **AllowCouponUnder500** - 允许金额<$500的代金券（条件: `context.input.amount < 500`）
4. **DenyCouponOver500** - 拒绝金额≥$500的代金券（条件: `context.input.amount >= 500`）

### Gateway Role权限
deploy.py会自动添加 `bedrock-agentcore:*` 权限到Gateway Role，确保Policy评估成功。

**注意**: 生产环境建议使用最小权限原则，仅授予必要的Policy评估权限：
- `bedrock-agentcore:GetPolicyEngine`
- `bedrock-agentcore:ListPolicies`
- `bedrock-agentcore:GetPolicy`
- `bedrock-agentcore:EvaluatePolicy`

### 部署优化
deploy.py采用**正确配置优先**策略：
- Gateway创建时就包含Machine + Web Client（无需后续update）
- Policy权限在部署前就配置（无需等待IAM传播）
- 自动清理失败的Policy规则并重建
- 自动查找已创建的Runtime（容错处理）

### 测试验证
部署完成后，可以通过前端测试：
- 尝试申请$100代金券 → 应该成功
- 尝试申请$500代金券 → 应该被Policy拒绝

## 🛠️ 故障排除

### prereq.sh失败
- 检查AWS凭证
- 确保有CloudFormation权限
- 查看CloudFormation控制台错误

### Runtime部署失败
- 检查CodeBuild日志
- 确保agent/tools.py中的导入正确
- 查看CloudWatch日志

### 前端无法访问
- 等待S3部署完成（1-2分钟）
- 检查bucket策略
- Token可能已过期

## 📈 监控

### CloudWatch日志
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/customer_support_agent-* --follow
```

### AgentCore Observability
AWS Console → CloudWatch → GenAI Observability → Bedrock AgentCore


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

