import { useState, useEffect } from 'react'
import { AppLayout, Header, Container, Button } from '@cloudscape-design/components'
import ChatInterface from './components/ChatInterface'
import WorkflowDiagram from './components/WorkflowDiagram'
import LoginPage from './components/LoginPage'
import authService from './services/authService'
import './App.css'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [activeNodes, setActiveNodes] = useState<string[]>([])
  const [traceEvents, setTraceEvents] = useState<any[]>([])
  const [stepDescriptions, setStepDescriptions] = useState<string[]>([])

  // 初始化认证服务
  useEffect(() => {
    // 从环境变量读取Cognito配置
    const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID
    const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
    const clientSecret = import.meta.env.VITE_COGNITO_CLIENT_SECRET || ''
    const region = import.meta.env.VITE_AWS_REGION || 'us-east-1'

    if (userPoolId && clientId) {
      authService.initialize({
        userPoolId,
        clientId,
        clientSecret,
        region,
      })

      // 检查是否已有有效token
      if (authService.isAuthenticated()) {
        setIsAuthenticated(true)
      }
    } else {
      console.warn('Cognito configuration not found in environment variables')
      // 如果没有配置，检查是否有预设token（向后兼容）
      const presetToken = import.meta.env.VITE_AUTH_TOKEN
      if (presetToken) {
        console.log('Using preset token from environment')
        setIsAuthenticated(true)
      }
    }
  }, [])

  const handleLoginSuccess = () => {
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    authService.logout()
    setIsAuthenticated(false)
    setActiveNodes([])
    setTraceEvents([])
    setStepDescriptions([])
  }

  // 如果未登录，显示登录页面
  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />
  }

  const handleTraceEvents = (events: any[]) => {
    console.log('📊 Received trace events:', events)
    
    // Fix tool node IDs for unknown tools
    const fixedEvents = events.map(event => {
      if (event.data?.node_id === 'tool-unknown' && event.data?.tool_name) {
        const toolName = event.data.tool_name.toLowerCase()
        let fixedNodeId = 'tool-unknown'
        
        if (toolName.includes('web_search')) {
          fixedNodeId = 'tool-websearch'
        } else if (toolName.includes('warranty')) {
          fixedNodeId = 'tool-warranty'
        } else if (toolName.includes('coupon')) {
          fixedNodeId = 'tool-coupon'
        } else if (toolName.includes('product')) {
          fixedNodeId = 'tool-product'
        } else if (toolName.includes('return') || toolName.includes('policy')) {
          fixedNodeId = 'tool-return'
        } else if (toolName.includes('technical') || toolName.includes('support') || toolName.includes('knowledge')) {
          fixedNodeId = 'tool-kb'
        }
        
        return {
          ...event,
          data: {
            ...event.data,
            node_id: fixedNodeId
          }
        }
      }
      return event
    })
    
    // Replace all events (not append) to reset state
    setTraceEvents(fixedEvents)
    
    // Extract active nodes from current events only
    const nodes = fixedEvents
      .filter(e => e.data?.node_id && e.data?.status !== 'complete')
      .map(e => e.data.node_id)
    
    console.log('🎯 Active nodes:', nodes)
    setActiveNodes([...new Set(nodes)])
    
    // Generate step descriptions
    const descriptions: string[] = []
    const nodeDescMap: Record<string, string> = {
      'user': '用户发送消息',
      'runtime': 'AgentCore Runtime 接收请求并启动处理',
      'agent': 'AI Agent 分析问题并决定如何响应',
      'memory': 'Memory 检索历史对话和用户偏好',
      'gateway': 'Gateway 路由工具调用请求',
      'policy': 'Policy 检查工具访问权限',
      'observability': 'Observability 记录所有操作日志',
      'evaluation': 'Evaluation 评估响应质量',
      'identity': 'Identity 验证用户身份和权限',
      'tool-product': '查询产品规格信息',
      'tool-return': '查询退货政策规则',
      'tool-websearch': '搜索网络获取最新信息',
      'tool-kb': '查询技术支持知识库',
      'tool-warranty': '检查产品保修状态',
      'tool-coupon': '查询优惠券信息',
    }
    
    fixedEvents.forEach(event => {
      const nodeId = event.data?.node_id
      if (nodeId && nodeDescMap[nodeId]) {
        if (!descriptions.includes(nodeDescMap[nodeId])) {
          descriptions.push(nodeDescMap[nodeId])
        }
      }
    })
    
    setStepDescriptions(descriptions)
  }

  return (
    <AppLayout
      navigationHide
      toolsHide
      contentType="default"
      headerSelector="#header"
      content={
        <>
          <div id="header" style={{ 
            background: 'white', 
            borderBottom: '1px solid #e5e7eb',
            padding: '12px 24px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 600 }}>
              AgentCore E2E 可视化演示
            </h1>
            <Button onClick={handleLogout} variant="normal">
              退出登录
            </Button>
          </div>
          <div style={{ 
            height: 'calc(100vh - 120px)', 
            display: 'grid', 
            gridTemplateColumns: '1fr 1fr 300px', 
            gap: '16px',
            padding: '16px',
          }}>
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <ChatInterface onTraceEvents={handleTraceEvents} />
            </div>
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <WorkflowDiagram 
                activeNodes={activeNodes}
                traceEvents={traceEvents}
              />
            </div>
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Container
                header={
                  <Header variant="h2">
                    执行步骤
                  </Header>
                }
              >
                <div style={{ 
                  height: 'calc(100vh - 240px)', 
                  overflowY: 'auto',
                  padding: '12px',
                }}>
                  {stepDescriptions.length === 0 ? (
                    <div style={{ color: '#666', fontSize: '14px', textAlign: 'center', padding: '20px' }}>
                      发送消息后，这里会显示系统执行的步骤
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {stepDescriptions.map((desc, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: '10px 12px',
                            background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
                            border: '1px solid #bae6fd',
                            borderRadius: '8px',
                            fontSize: '13px',
                            color: '#0c4a6e',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            animation: 'slideIn 0.3s ease-out',
                          }}
                        >
                          <span style={{ 
                            background: '#0ea5e9', 
                            color: 'white', 
                            borderRadius: '50%', 
                            width: '20px', 
                            height: '20px', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center',
                            fontSize: '11px',
                            fontWeight: 'bold',
                            flexShrink: 0,
                          }}>
                            {idx + 1}
                          </span>
                          <span style={{ flex: 1 }}>{desc}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Container>
            </div>
          </div>
        </>
      }
    />
  )
}

export default App
