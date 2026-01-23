/**
 * Workflow Diagram Configuration
 * 
 * 调整说明:
 * - position: 节点位置 {x, y}
 * - width/height: 节点尺寸
 * - sourceHandle/targetHandle: 连接点位置 ('top', 'bottom', 'left', 'right')
 * - type: 连线类型 ('straight' 直线, 'smoothstep' 平滑曲线)
 */

import { Node, Edge, MarkerType } from '@xyflow/react'

// 节点尺寸配置
export const nodeStyles = {
  service: {
    minWidth: 140,
    minHeight: 80,
    padding: 12,
    borderRadius: 12,
  },
  agent: {
    minWidth: 140,
    minHeight: 100,
    padding: 16,
    borderRadius: 16,
  },
  tool: {
    minWidth: 110,
    minHeight: 70,
    padding: 10,
    borderRadius: 8,
  },
}

// 节点配置
export const initialNodes: Node[] = [
  // 垂直中心线: x = 400
  {
    id: 'user',
    type: 'service',
    position: { x: 400, y: 40 },
    data: { 
      label: '客户端Chatbot', 
      description: '用户输入', 
      status: 'idle', 
      icon: '👤', 
      color: '#6366f1',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
    },
  },
  {
    id: 'runtime',
    type: 'service',
    position: { x: 400, y: 160 },
    data: { 
      label: 'AgentCore Runtime', 
      description: '执行环境', 
      status: 'idle', 
      icon: '🚀', 
      color: '#ec4899',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
      clickUrl: '/runtime-code.html',
    },
  },
  {
    id: 'agent',
    type: 'agent',
    position: { x: 400, y: 280 },
    data: { 
      label: 'Customer Support Agent', 
      description: 'Main AI Agent', 
      status: 'idle', 
      thinking: false, 
      color: '#3b82f6', 
      icon: '🤖',
      width: nodeStyles.agent.minWidth,
      height: nodeStyles.agent.minHeight,
    },
  },
  {
    id: 'gateway',
    type: 'service',
    position: { x: 400, y: 420 },
    data: { 
      label: 'AgentCore Gateway', 
      description: 'MCP Router', 
      status: 'idle', 
      icon: '🔀', 
      color: '#6b7280',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
    },
  },
  
  // 水平线: y = 280 (与agent对齐)
  {
    id: 'memory',
    type: 'service',
    position: { x: 150, y: 280 },
    data: { 
      label: 'AgentCore Memory', 
      description: 'Conversation Context', 
      status: 'idle', 
      icon: '🧠', 
      color: '#8b5cf6',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
    },
  },
  {
    id: 'observability',
    type: 'service',
    position: { x: 650, y: 280 },
    data: { 
      label: 'AgentCore Observability', 
      description: 'Monitoring', 
      status: 'idle', 
      icon: '📊', 
      color: '#10b981',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
      clickUrl: 'https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core/agent-alias/customer_support_agent-H7nWPc20af/endpoint/DEFAULT/agent/customer_support_agent?resourceId=arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A585306731051%3Aruntime%2Fcustomer_support_agent-H7nWPc20af%2Fruntime-endpoint%2FDEFAULT%3ADEFAULT&serviceName=customer_support_agent.DEFAULT',
    },
  },
  {
    id: 'evaluation',
    type: 'service',
    position: { x: 650, y: 160 },
    data: { 
      label: 'AgentCore Evaluation', 
      description: 'Quality Metrics', 
      status: 'idle', 
      icon: '📈', 
      color: '#f59e0b',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
      clickUrl: 'https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#/gen-ai-observability/agent-core/agent-alias/customer_support_agent-H7nWPc20af/endpoint/DEFAULT/agent/customer_support_agent?resourceId=arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3A585306731051%3Aruntime%2Fcustomer_support_agent-H7nWPc20af%2Fruntime-endpoint%2FDEFAULT%3ADEFAULT&serviceName=customer_support_agent.DEFAULT&tabId=evaluations',
    },
  },
  {
    id: 'policy',
    type: 'service',
    position: { x: 580, y: 420 },
    data: { 
      label: 'AgentCore Policy', 
      description: '访问控制', 
      status: 'idle', 
      icon: '🛡️', 
      color: '#8b5cf6',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
      clickUrl: 'https://us-east-1.console.aws.amazon.com/bedrock-agentcore/policy/CustomerSupport_PolicyEngine-sv4oem2ru0',
    },
  },
  {
    id: 'identity',
    type: 'service',
    position: { x: 200, y: 420 },
    data: { 
      label: 'AgentCore Identity', 
      description: 'Authentication', 
      status: 'idle', 
      icon: '🔐', 
      color: '#dc2626',
      width: nodeStyles.service.minWidth,
      height: nodeStyles.service.minHeight,
    },
  },
  
  // 工具层: y = 560, 6个工具水平均匀分布
  {
    id: 'tool-product',
    type: 'tool',
    position: { x: 50, y: 560 },
    data: { 
      label: 'Product Info', 
      description: 'get_product_info', 
      status: 'idle',
      width: nodeStyles.tool.minWidth,
      height: nodeStyles.tool.minHeight,
    },
  },
  {
    id: 'tool-return',
    type: 'tool',
    position: { x: 190, y: 560 },
    data: { 
      label: 'Return Policy', 
      description: 'get_return_policy', 
      status: 'idle',
      width: nodeStyles.tool.minWidth,
      height: nodeStyles.tool.minHeight,
    },
  },
  {
    id: 'tool-kb',
    type: 'tool',
    position: { x: 330, y: 560 },
    data: { 
      label: 'Knowledge Base', 
      description: 'get_technical_support', 
      status: 'idle',
      width: nodeStyles.tool.minWidth,
      height: nodeStyles.tool.minHeight,
    },
  },
  {
    id: 'tool-warranty',
    type: 'tool',
    position: { x: 470, y: 560 },
    data: { 
      label: 'Warranty Check', 
      description: 'check_warranty_status', 
      status: 'idle',
      width: nodeStyles.tool.minWidth,
      height: nodeStyles.tool.minHeight,
    },
  },
  {
    id: 'tool-websearch',
    type: 'tool',
    position: { x: 610, y: 560 },
    data: { 
      label: 'Web Search', 
      description: 'web_search', 
      status: 'idle',
      width: nodeStyles.tool.minWidth,
      height: nodeStyles.tool.minHeight,
    },
  },
  {
    id: 'tool-coupon',
    type: 'tool',
    position: { x: 750, y: 560 },
    data: { 
      label: 'Coupon Tool', 
      description: '代金券批复', 
      status: 'idle',
      width: nodeStyles.tool.minWidth,
      height: nodeStyles.tool.minHeight,
      clickUrl: '/coupon-code.html',
    },
  },
]

// 边配置
// 提示: 如果连线不正确,可以添加 sourceHandle 和 targetHandle
// 可用值: 'top', 'bottom', 'left', 'right'
export const initialEdges: Edge[] = [
  // 垂直中心线连接 (直线)
  { 
    id: 'e1', 
    source: 'user', 
    sourceHandle: 'bottom',
    target: 'runtime', 
    type: 'straight', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e2', 
    source: 'runtime', 
    sourceHandle: 'bottom',
    target: 'agent', 
    type: 'straight', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e5', 
    source: 'agent', 
    target: 'gateway', 
    type: 'straight', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  
  // 水平连接 (直线)
  { 
    id: 'e3', 
    source: 'agent', 
    sourceHandle: 'left',
    target: 'memory',
    targetHandle: 'right', 
    type: 'straight', 
    animated: false 
  },
  { 
    id: 'e4', 
    source: 'agent', 
    sourceHandle: 'right',
    target: 'observability', 
    targetHandle: 'left', 
    type: 'straight', 
    animated: false 
  },
  { 
    id: 'e11', 
    source: 'evaluation', 
    sourceHandle: 'bottom',
    target: 'observability', 
    targetHandle: 'top', 
    type: 'straight', 
    animated: false 
  },
  { 
    id: 'e13', 
    source: 'gateway', 
    sourceHandle: 'right',
    target: 'policy', 
    targetHandle: 'left', 
    type: 'straight', 
    animated: false 
  },
  { 
    id: 'e6', 
    source: 'identity', 
    sourceHandle: 'right',
    target: 'gateway', 
    targetHandle: 'left', 
    type: 'straight', 
    animated: false 
  },
  
  // Gateway到工具 (平滑曲线)
  { 
    id: 'e7', 
    source: 'gateway', 
    sourceHandle: 'bottom',
    target: 'tool-product', 
    type: 'smoothstep', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e8', 
    source: 'gateway', 
    sourceHandle: 'bottom',
    target: 'tool-return', 
    type: 'smoothstep', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e9', 
    source: 'gateway', 
    sourceHandle: 'bottom',
    target: 'tool-kb', 
    type: 'smoothstep', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e10', 
    source: 'gateway', 
    sourceHandle: 'bottom',
    target: 'tool-warranty', 
    type: 'smoothstep', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e12', 
    source: 'gateway', 
    sourceHandle: 'bottom',
    target: 'tool-websearch', 
    type: 'smoothstep', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
  { 
    id: 'e14', 
    source: 'gateway', 
    sourceHandle: 'bottom',
    target: 'tool-coupon', 
    type: 'smoothstep', 
    markerEnd: { type: MarkerType.ArrowClosed }, 
    animated: false 
  },
]
