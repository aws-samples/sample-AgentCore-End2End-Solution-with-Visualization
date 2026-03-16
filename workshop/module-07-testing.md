# 模块 7: 端到端测试

> ⏱️ 预计时间：15 分钟

## 学习目标

- 使用前端界面测试所有 Agent 功能
- 观察工作流可视化的实时效果
- 验证 Policy Engine 的访问控制
- 通过 AWS Console 查看 Observability 数据

---

## 7.1 访问前端

### 获取 CloudFront URL

`deploy.py` 完成后会输出 CloudFront URL。如果您错过了输出，可以通过以下方式获取：

**方式 1：从 deployment_info.yaml 读取**

```bash
cat deployment_info.yaml | grep frontend_url
```

输出示例：
```
frontend_url: https://d184782ixc11gq.cloudfront.net
```

**方式 2：从 AWS Console 查看**

1. 打开 [CloudFront Console](https://console.aws.amazon.com/cloudfront)
2. 找到 Comment 包含 `agentcore-frontend` 的分发
3. 复制 Domain name（如 `d184782ixc11gq.cloudfront.net`）
4. 访问 `https://<domain-name>`

**方式 3：通过 AWS CLI 查询**

```bash
aws cloudfront list-distributions \
  --query 'DistributionList.Items[?contains(Comment, `agentcore-frontend`)].DomainName' \
  --output text
```

> ⏳ CloudFront 首次部署后需要 5-10 分钟生效。如果访问返回错误，请稍等片刻再试。

### 登录

打开 CloudFront URL，您会看到登录页面。使用测试账号登录：

- 用户名：`testuser@example.com`
- 密码：`MyPassword123!`

登录成功后，您会看到三栏布局：左侧聊天界面、中间工作流可视化、右侧执行步骤。

> 💡 **备选方案**：如果 CloudFront 尚未生效，也可以在本地运行前端（需要 Node.js 18+）：
> ```bash
> cd frontend && npm install && npm run dev
> ```
> 然后访问 http://localhost:3000

---

## 7.2 测试场景 1: 产品信息查询

### 输入
```
What are the specifications for your laptops?
```

### 预期行为
- Agent 调用本地工具 `get_product_info`
- 不经过 Gateway（本地工具直接调用）
- 返回笔记本电脑的规格信息

### 工作流可视化
```
👤 User → 🚀 Runtime → 🤖 Agent → 🔧 Product Info → 📊 Observability
```

### 预期响应
Agent 会返回包含以下信息的回复：
- 保修：1年制造商保修 + 可选延保
- 规格：Intel/AMD 处理器、8-32GB RAM、SSD 存储
- 特性：背光键盘、USB-C/Thunderbolt、Wi-Fi 6

---

## 7.3 测试场景 2: 保修查询

### 输入
```
Check warranty for serial number ABC12345678, my email is john.smith@email.com
```

> 💡 **提示**：`check_warranty_status` 工具有一个可选的 `customer_email` 参数。如果只输入序列号不带 email，Agent 可能会先追问您的邮箱再调用工具。在输入中直接提供 email 可以让 Agent 一步到位。

### 预期行为
- Agent 调用 Gateway 工具 `check_warranty_status`
- Gateway 进行 Policy 检查（AllowCheckWarranty → ALLOW）
- Lambda 查询 DynamoDB 返回保修信息

### 工作流可视化
```
👤 User → 🚀 Runtime → 🤖 Agent → 🔀 Gateway → 🛡️ Policy(✅) → 🔧 Warranty Check → 📊 Observability
```

### 预期响应
Agent 会返回 ABC12345678 的保修信息：
- 产品：SmartPhone Pro Max 128GB
- 购买日期：2023-01-15
- 保修到期：2025-01-15
- 保修类型：Extended Warranty

---

## 7.4 测试场景 3: 代金券申请（Policy 允许）⭐

### 输入
```
I need a $100 coupon
```

### 预期行为
- Agent 调用 Gateway 工具 `CouponTool(amount=100)`
- Policy Engine 评估：`context.input.amount(100) < 500` → **ALLOW** ✅
- Lambda 执行代金券批复

### 工作流可视化
```
👤 User → 🚀 Runtime → 🤖 Agent → 🔀 Gateway → 🛡️ Policy(✅ Allow) → 🔧 Coupon Tool → 📊 Observability
```

### 预期响应
```
✅ 代金券批复成功！金额: $100
代金券代码: COUPON-10000
```

---

## 7.5 测试场景 4: 代金券申请（Policy 拒绝）⭐

### 输入
```
I need a $500 coupon
```

### 预期行为
- Agent 调用 Gateway 工具 `CouponTool(amount=500)`
- Policy Engine 评估：`context.input.amount(500) >= 500` → **DENY** ❌
- Lambda 不会被调用
- Gateway 返回拒绝信息

### 工作流可视化
```
👤 User → 🚀 Runtime → 🤖 Agent → 🔀 Gateway → 🛡️ Policy(❌ Deny) → 📊 Observability
```

### 预期响应
Agent 会告知用户代金券请求被拒绝，可能建议申请较小金额的代金券。

> 💡 **对比场景 3 和 4**：同样的工具调用，不同的金额参数，Policy Engine 做出了不同的决策。这就是条件化访问控制的威力。

---

## 7.6 测试场景 5: 技术支持

### 输入
```
How do I calibrate my monitor?
```

### 预期行为
- Agent 调用本地工具 `get_technical_support`
- 工具查询 Bedrock Knowledge Base
- 返回 `knowledge_base_data/` 中的相关文档内容

### 工作流可视化
```
👤 User → 🚀 Runtime → 🤖 Agent → 🔧 Knowledge Base → 📊 Observability
```

---

## 7.7 测试场景 6: 网页搜索

### 输入
```
Search for iPhone 15 troubleshooting tips
```

### 预期行为
- Agent 调用 Gateway 工具 `web_search`
- Gateway 进行 Policy 检查（AllowWebSearch → ALLOW）
- Lambda 使用 DuckDuckGo 搜索

### 工作流可视化
```
👤 User → 🚀 Runtime → 🤖 Agent → 🔀 Gateway → 🛡️ Policy(✅) → 🔧 Web Search → 📊 Observability
```

---

## 7.8 查看 Observability

### CloudWatch GenAI Observability

1. 点击前端 Header 中的 **📊 Observability** 链接
2. 或手动打开：AWS Console → CloudWatch → GenAI Observability → Bedrock AgentCore
3. 选择您的 Runtime

您可以看到：
- 请求追踪（每次对话的完整链路）
- 延迟指标
- 错误率
- 工具调用统计

### CloudWatch 日志

```bash
# 查看 Runtime 日志
aws logs tail /aws/bedrock-agentcore/runtimes/customer_support_agent-* --follow
```

### Policy Engine Console

1. 点击前端 Header 中的 **🔐 Policy Engine** 链接
2. 查看 Policy 评估历史
3. 确认 $100 代金券被 ALLOW，$500 代金券被 DENY

---

## 7.9 测试结果汇总

| 场景 | 工具 | Policy | 结果 |
|------|------|--------|------|
| 产品查询 | get_product_info（本地） | N/A | ✅ 返回产品信息 |
| 保修查询 | check_warranty_status（Gateway） | ALLOW | ✅ 返回保修信息 |
| $100 代金券 | CouponTool（Gateway） | ALLOW | ✅ 批复成功 |
| $500 代金券 | CouponTool（Gateway） | DENY | ❌ 被拒绝 |
| 技术支持 | get_technical_support（本地） | N/A | ✅ 返回 KB 内容 |
| 网页搜索 | web_search（Gateway） | ALLOW | ✅ 返回搜索结果 |

---

## 7.10 常见问题排查

### 登录失败
- 确认 Web Client 已启用 `USER_PASSWORD_AUTH`
- 确认测试用户已创建
- 检查 Cognito User Pool 状态

### Agent 无响应
- 检查 Runtime 状态是否为 ACTIVE
- 查看 CloudWatch 日志
- 确认 Runtime ARN 配置正确

### Policy 不生效
- 确认 Policy Engine 已关联到 Gateway
- 确认所有 Policy 规则状态为 ACTIVE
- 确认 Gateway Role 有 Policy 评估权限
- 等待 IAM 权限传播（最多 30 秒）

### 工具调用失败
- 确认 Gateway Target 配置正确
- 确认 Lambda 函数可以正常执行
- 检查 Gateway Role 的 Lambda 调用权限

---

## ✅ 检查清单

- [ ] 产品信息查询正常
- [ ] 保修查询正常
- [ ] $100 代金券批复成功
- [ ] $500 代金券被 Policy 拒绝
- [ ] 工作流可视化正确显示
- [ ] 能在 CloudWatch 中看到 Observability 数据

---

[⬅️ 上一模块: 前端可视化](./module-06-frontend.md) | [下一模块: 清理资源 ➡️](./module-08-cleanup.md)
