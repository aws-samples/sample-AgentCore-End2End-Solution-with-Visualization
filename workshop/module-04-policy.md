# 模块 4: Policy Engine

> ⏱️ 预计时间：15 分钟

## 学习目标

- 理解 AgentCore Policy Engine 的作用
- 学习 Cedar 策略语言的基本语法
- 创建条件化的访问控制规则
- 将 Policy Engine 关联到 Gateway

---

## 4.1 什么是 Policy Engine？

AgentCore Policy Engine 是一个基于 **Cedar 策略语言** 的访问控制引擎。它可以在 Gateway 层面控制哪些工具可以被调用，以及在什么条件下可以调用。

### 为什么需要 Policy Engine？

在 AI Agent 系统中，工具调用的安全控制至关重要：

- 🛡️ **防止滥用** - 限制高风险操作（如大额代金券）
- 📋 **合规审计** - 记录所有工具调用的授权决策
- 🔒 **最小权限** - 只允许必要的工具访问
- 📊 **可观测性** - 在 ENFORCE 或 LOG_ONLY 模式下运行

### 工作流程

```
Agent 调用工具
      │
      ▼
┌─────────────┐
│   Gateway   │
│  收到请求   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│ Policy Engine│────▶│ Cedar 规则   │
│  评估请求   │     │ 评估         │
└──────┬──────┘     └──────────────┘
       │
   ┌───┴───┐
   │       │
   ▼       ▼
 ALLOW   DENY
   │       │
   ▼       ▼
执行工具  返回拒绝
```

---

## 4.2 Cedar 策略语言

Cedar 是 AWS 开发的一种声明式策略语言，语法简洁直观。

### 基本结构

```cedar
permit(                              // 或 forbid
    principal is AgentCore::OAuthUser,  // 谁
    action == AgentCore::Action::"工具名",  // 做什么
    resource == AgentCore::Gateway::"Gateway ARN"  // 在哪里
) when {                             // 条件（可选）
    context.input.amount < 500
};
```

### 关键概念

| 概念 | 说明 | 示例 |
|------|------|------|
| `permit` | 允许操作 | 允许查询保修 |
| `forbid` | 拒绝操作 | 拒绝大额代金券 |
| `principal` | 请求者身份 | OAuth 用户 |
| `action` | 要执行的操作 | 工具名称 |
| `resource` | 目标资源 | Gateway ARN |
| `when` | 条件子句 | 金额限制 |
| `context.input` | 工具输入参数 | amount 参数 |

---

## 4.3 本系统的 4 个 Policy 规则

> 📁 **源文件**：`utils/agentcore_helper.py` → `create_policy_rules` 函数（第 430-490 行）
> 
> 这 4 条 Cedar 规则以 Python f-string 形式定义在代码中，`{gateway_arn}` 在部署时动态替换为实际的 Gateway ARN。

### 规则 1: AllowCheckWarranty

```cedar
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"LambdaTools___check_warranty_status",
    resource == AgentCore::Gateway::"{gateway_arn}"
);
```
→ 无条件允许保修查询

### 规则 2: AllowWebSearch

```cedar
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"LambdaTools___web_search",
    resource == AgentCore::Gateway::"{gateway_arn}"
);
```
→ 无条件允许网页搜索

### 规则 3: AllowCouponUnder500 ⭐

```cedar
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"CouponToolTarget___CouponTool",
    resource == AgentCore::Gateway::"{gateway_arn}"
) when {
    context.input.amount < 500
};
```
→ 只允许金额小于 $500 的代金券

### 规则 4: DenyCouponOver500 ⭐

```cedar
forbid(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"CouponToolTarget___CouponTool",
    resource == AgentCore::Gateway::"{gateway_arn}"
) when {
    context.input.amount >= 500
};
```
→ 明确拒绝金额 ≥ $500 的代金券

> 💡 **为什么需要同时定义 permit 和 forbid？**
> Cedar 采用"默认拒绝"策略。没有匹配的 permit 规则时，请求会被拒绝。但显式的 forbid 规则可以提供更清晰的审计日志，明确表示这是一个有意的拒绝。

---

## 4.4 创建 Policy Engine

> 📁 **源文件**：`utils/agentcore_helper.py` → `create_policy_engine`、`create_policy_rules`、`attach_policy_to_gateway` 函数
> 📁 **部署入口**：`deploy.py` → `deploy_policy_engine` 方法
> 📁 **配置**：`config.yaml` → `policy` 部分

### 代码解析

```python
def create_policy_engine(engine_name, region):
    """创建 Policy Engine"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    response = gateway_client.create_policy_engine(
        name=engine_name,
        description="Customer Support Gateway Policy Engine"
    )
    
    return response["policyEngineId"]
```

### 创建 Policy 规则

```python
def create_policy_rules(policy_engine_id, gateway_arn, region):
    """创建 4 个 Cedar 规则"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    policies = [
        {
            "name": "AllowCheckWarranty",
            "statement": f"""permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"LambdaTools___check_warranty_status",
    resource == AgentCore::Gateway::"{gateway_arn}"
);"""
        },
        # ... 其他规则
    ]
    
    for policy in policies:
        gateway_client.create_policy(
            name=f"CustomerSupport_{policy['name']}",
            definition={
                "cedar": {
                    "statement": policy["statement"]
                }
            },
            policyEngineId=policy_engine_id,
            validationMode="IGNORE_ALL_FINDINGS"
        )
```

### 关联到 Gateway

```python
def attach_policy_to_gateway(gateway_id, policy_engine_id, mode, region):
    """将 Policy Engine 关联到 Gateway"""
    gateway_client.update_gateway(
        gatewayIdentifier=gateway_id,
        policyEngineConfiguration={
            "arn": policy_engine_arn,
            "mode": mode  # "ENFORCE" 或 "LOG_ONLY"
        }
    )
```

---

## 4.5 Policy 模式

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `ENFORCE` | 实际执行允许/拒绝 | 生产环境 |
| `LOG_ONLY` | 只记录决策，不实际拒绝 | 测试和调试 |

本 Workshop 使用 `ENFORCE` 模式，这样您可以直观地看到 Policy 的效果。

---

## 4.6 IAM 权限要求

> 📁 **源文件**：`deploy.py` → `ensure_gateway_policy_permissions` 方法

Gateway Role 需要有 Policy Engine 的评估权限：

```python
# deploy.py 自动添加的权限
policy_engine_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "bedrock-agentcore:*",
            "Resource": "*"
        }
    ]
}
```

> ⚠️ **生产环境建议**：使用最小权限原则，只授予必要的权限：
> - `bedrock-agentcore:GetPolicyEngine`
> - `bedrock-agentcore:ListPolicies`
> - `bedrock-agentcore:EvaluatePolicy`

---

## 4.7 验证 Policy Engine

```bash
# 获取 Policy Engine ID
PE_ID=$(python3 -c "
import yaml
with open('deployment_info.yaml') as f:
    info = yaml.safe_load(f)
print(info.get('policy_engine_id', 'N/A'))
")

# 列出 Policy 规则
aws bedrock-agentcore-control list-policies \
  --policy-engine-id $PE_ID \
  --query 'policies[].{name:name, status:status}'
```

所有规则应该显示 `ACTIVE` 状态。

### 在 Console 中查看

打开 AWS Console → Bedrock AgentCore → Policy Engines，可以看到：
- Policy Engine 详情
- 4 个 Cedar 规则
- 每个规则的状态

---

## 4.8 测试场景预览

部署完成后，您将在模块 7 中测试以下场景：

| 请求 | Policy 决策 | 结果 |
|------|------------|------|
| "I need a $100 coupon" | ✅ ALLOW（amount=100 < 500） | Lambda 执行，返回代金券 |
| "I need a $500 coupon" | ❌ DENY（amount=500 ≥ 500） | 不调用 Lambda，返回拒绝 |
| "Check warranty for ABC12345678" | ✅ ALLOW（无条件） | Lambda 执行，返回保修信息 |
| "Search for iPhone troubleshooting" | ✅ ALLOW（无条件） | Lambda 执行，返回搜索结果 |

---

## ✅ 检查清单

- [ ] 理解 Cedar 策略语言的基本语法
- [ ] 理解 4 个 Policy 规则的作用
- [ ] 理解 ENFORCE 和 LOG_ONLY 模式的区别
- [ ] Policy Engine 创建成功，所有规则状态为 ACTIVE
- [ ] Policy Engine 已关联到 Gateway

---

[⬅️ 上一模块: AgentCore Gateway](./module-03-gateway.md) | [下一模块: AgentCore Runtime ➡️](./module-05-runtime.md)
