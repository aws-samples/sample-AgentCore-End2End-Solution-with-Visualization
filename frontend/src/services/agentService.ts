import axios from 'axios'
import authService from './authService'

// Configuration - should be set via environment variables
const AGENT_RUNTIME_ARN = import.meta.env.VITE_AGENT_RUNTIME_ARN || ''
const AWS_REGION = import.meta.env.VITE_AWS_REGION || 'us-east-1'
const PRESET_AUTH_TOKEN = import.meta.env.VITE_AUTH_TOKEN || '' // 向后兼容

interface AgentResponse {
  response: string
  events: any[]
  streaming?: boolean
}

/**
 * 获取认证token（优先使用登录token，其次使用预设token）
 */
function getAuthToken(): string {
  const loginToken = authService.getAccessToken()
  return loginToken || PRESET_AUTH_TOKEN
}

/**
 * Invoke the AgentCore Runtime endpoint
 */
export async function invokeAgent(prompt: string): Promise<AgentResponse> {
  try {
    const authToken = getAuthToken()
    
    if (!authToken) {
      throw new Error('No authentication token available. Please login.')
    }
    
    // 直接调用AgentCore Runtime API
    const runtimeArn = AGENT_RUNTIME_ARN
    if (!runtimeArn) {
      throw new Error('Runtime ARN not configured')
    }
    
    // URL encode the runtime ARN
    const escapedArn = encodeURIComponent(runtimeArn)
    const endpoint = `https://bedrock-agentcore.${AWS_REGION}.amazonaws.com/runtimes/${escapedArn}/invocations`
    
    // Generate session ID (for logging, not sent as header)
    const sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    console.log('Session ID:', sessionId)
    
    const response = await axios.post<AgentResponse>(
      endpoint,
      {
        prompt: prompt,
      },
      {
        params: {
          qualifier: 'DEFAULT'
        },
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        timeout: 120000,
      }
    )

    return response.data
  } catch (error) {
    console.error('Error invoking agent:', error)
    
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) {
        authService.logout()
        throw new Error('认证已过期，请重新登录')
      }
      throw new Error(error.response?.data?.message || error.message)
    }
    
    throw error
  }
}

/**
 * Get agent configuration
 */
export function getAgentConfig() {
  const authToken = getAuthToken()
  
  return {
    runtimeArn: AGENT_RUNTIME_ARN,
    region: AWS_REGION,
    hasAuth: !!authToken,
    isUsingLoginToken: !!authService.getAccessToken(),
  }
}
