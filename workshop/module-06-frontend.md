# 模块 6: 前端可视化

> ⏱️ 预计时间：15 分钟

## 学习目标

- 理解前端架构和技术栈
- 了解工作流可视化的实现原理
- 部署前端到 CloudFront 或本地运行
- 理解前端如何与 AgentCore Runtime 交互

---

## 6.1 前端技术栈

| 技术 | 用途 |
|------|------|
| React 18 | UI 框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Cloudscape Design System | AWS 风格 UI 组件库 |
| React Flow (@xyflow/react) | 工作流图可视化 |
| Axios | HTTP 请求 |
| CryptoJS | Cognito SECRET_HASH 计算 |

---

## 6.2 前端架构

```
frontend/src/
├── App.tsx                    # 主应用（布局 + 路由）
├── components/
│   ├── LoginPage.tsx          # 登录页面
│   ├── ChatInterface.tsx      # 聊天界面
│   ├── WorkflowDiagram.tsx    # 工作流可视化
│   └── nodes/                 # 自定义节点组件
│       ├── AgentNode.tsx      # Agent 节点
│       ├── ServiceNode.tsx    # 服务节点
│       └── ToolNode.tsx       # 工具节点
├── services/
│   ├── authService.ts         # Cognito 认证服务
│   └── agentService.ts        # Agent API 调用
└── config/
    └── workflowConfig.ts      # 工作流图配置
```

### 页面布局

```
┌──────────────────────────────────────────────────────┐
│  AgentCore E2E 可视化演示  [Observability] [Policy]  │
├──────────────┬──────────────────┬────────────────────┤
│              │                  │                    │
│   Chat       │   Workflow       │   执行步骤         │
│   Interface  │   Visualization  │                    │
│              │                  │   1. 用户发送消息   │
│   [用户消息]  │   ┌──┐          │   2. Runtime 处理   │
│   [Agent回复] │   │🤖│→ ┌──┐   │   3. Agent 思考     │
│              │   └──┘  │🔀│   │   4. Gateway 路由   │
│              │         └──┘   │   5. Policy 检查    │
│              │                  │   6. 工具调用       │
│   [输入框]   │                  │                    │
│              │                  │                    │
└──────────────┴──────────────────┴────────────────────┘
```

---

## 6.3 认证流程

### Cognito 登录 (`authService.ts`)

```typescript
class AuthService {
  async login(username: string, password: string): Promise<AuthTokens> {
    const endpoint = `https://cognito-idp.${region}.amazonaws.com/`
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
      },
      body: JSON.stringify({
        AuthFlow: 'USER_PASSWORD_AUTH',
        ClientId: this.config.clientId,
        AuthParameters: {
          USERNAME: username,
          PASSWORD: password,
        },
      }),
    })
    
    // 保存 tokens 到 localStorage
    this.tokens = {
      accessToken: data.AuthenticationResult.AccessToken,
      idToken: data.AuthenticationResult.IdToken,
      refreshToken: data.AuthenticationResult.RefreshToken,
    }
  }
}
```

> 💡 Web Client 没有 Secret，所以不需要计算 SECRET_HASH。

### 调用 Runtime (`agentService.ts`)

```typescript
export async function invokeAgent(prompt: string): Promise<AgentResponse> {
  const authToken = authService.getAccessToken()
  
  // 直接调用 AgentCore Runtime API
  const escapedArn = encodeURIComponent(AGENT_RUNTIME_ARN)
  const endpoint = `https://bedrock-agentcore.${AWS_REGION}.amazonaws.com/runtimes/${escapedArn}/invocations`
  
  const response = await axios.post(endpoint, 
    { prompt },
    {
      params: { qualifier: 'DEFAULT' },
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      timeout: 120000,
    }
  )
  
  return response.data
}
```

---

## 6.4 工作流可视化

### 节点配置 (`workflowConfig.ts`)

工作流图定义了系统中的所有组件和它们之间的连接：

```typescript
// 节点定义
export const initialNodes: Node[] = [
  // 核心链路（垂直）
  { id: 'user',     type: 'service', label: '客户端Chatbot',        icon: '👤' },
  { id: 'runtime',  type: 'service', label: 'AgentCore Runtime',    icon: '🚀' },
  { id: 'agent',    type: 'agent',   label: 'Customer Support Agent', icon: '🤖' },
  { id: 'gateway',  type: 'service', label: 'AgentCore Gateway',    icon: '🔀' },
  
  // 辅助服务（水平）
  { id: 'memory',       type: 'service', label: 'AgentCore Memory',       icon: '🧠' },
  { id: 'observability', type: 'service', label: 'AgentCore Observability', icon: '📊' },
  { id: 'policy',       type: 'service', label: 'AgentCore Policy',       icon: '🛡️' },
  { id: 'identity',     type: 'service', label: 'AgentCore Identity',     icon: '🔐' },
  
  // 工具层
  { id: 'tool-product',   type: 'tool', label: 'Product Info' },
  { id: 'tool-return',    type: 'tool', label: 'Return Policy' },
  { id: 'tool-kb',        type: 'tool', label: 'Knowledge Base' },
  { id: 'tool-warranty',  type: 'tool', label: 'Warranty Check' },
  { id: 'tool-websearch', type: 'tool', label: 'Web Search' },
  { id: 'tool-coupon',    type: 'tool', label: 'Coupon Tool' },
]
```

### Trace Events 驱动可视化

Agent 返回的 `events` 数组驱动工作流图的动画：

```typescript
// 事件类型 → 节点状态映射
const eventTypeMap = {
  'user_input':      { nodeId: 'user',    status: 'active' },
  'runtime_start':   { nodeId: 'runtime', status: 'processing' },
  'agent_start':     { nodeId: 'agent',   status: 'thinking' },
  'memory_access':   { nodeId: 'memory',  status: 'processing' },
  'gateway_routing': { nodeId: 'gateway', status: 'routing' },
  'policy_check':    { nodeId: 'policy',  status: 'checking' },
  'tool_call':       { nodeId: 'tool-*',  status: 'calling' },
  'tool_result':     { nodeId: 'tool-*',  status: 'complete' },
  'response':        { nodeId: 'runtime', status: 'complete' },
}
```

当收到 trace events 时，对应的节点会高亮显示，连接线会动画流动，让用户直观地看到请求在系统中的流转过程。

---

## 6.5 部署前端

### 方式 1: 本地开发（推荐用于 Workshop）

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

### 方式 2: CloudFront 部署

`deploy.py` 会自动完成以下步骤：

1. 生成 `.env` 文件（包含 Runtime ARN、Cognito 配置等）
2. `npm install` + `npm run build`
3. 创建 S3 Bucket
4. 上传构建产物到 S3
5. 创建 CloudFront 分发 + OAI
6. 配置 S3 Bucket Policy
7. 失效 CloudFront 缓存

### 前端环境变量

`.env` 文件内容：

```bash
# Runtime 配置
VITE_AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/customer_support_agent-xxxxx
VITE_AWS_REGION=us-east-1

# AgentCore 资源 ID（用于 Console 链接）
VITE_POLICY_ENGINE_ID=CustomerSupport_PolicyEngine-xxxxx
VITE_GATEWAY_ID=customersupport-gw-xxxxx
VITE_MEMORY_ID=customersupportmemory-xxxxx

# Cognito 配置
VITE_COGNITO_USER_POOL_ID=us-east-1_xxxxxxx
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 6.6 前端功能一览

### 登录页面
- 使用 Cognito USER_PASSWORD_AUTH 流程
- 默认填充测试账号信息
- Token 自动保存到 localStorage

### 聊天界面
- 实时对话
- Markdown 格式化
- 加载状态指示

### 工作流可视化
- 实时显示请求流转路径
- 节点状态动画（idle → processing → complete）
- 连接线流动动画
- 支持重置

### 执行步骤面板
- 按顺序显示每个执行步骤
- 中文描述

### Header 快捷链接
- 📊 Observability - 跳转到 CloudWatch GenAI Observability
- 🔐 Policy Engine - 跳转到 Policy Engine Console
- 📈 Evaluation - 跳转到 Evaluation Console

---

## ✅ 检查清单

- [ ] 理解前端的三栏布局
- [ ] 理解 Cognito 登录流程
- [ ] 理解 trace events 如何驱动工作流可视化
- [ ] 前端可以正常访问（本地或 CloudFront）
- [ ] 能够成功登录

---

[⬅️ 上一模块: AgentCore Runtime](./module-05-runtime.md) | [下一模块: 端到端测试 ➡️](./module-07-testing.md)
