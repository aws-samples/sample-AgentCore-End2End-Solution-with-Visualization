/**
 * Cognito认证服务
 * 处理用户登录、token管理
 */

import CryptoJS from 'crypto-js'

interface CognitoConfig {
  userPoolId: string
  clientId: string
  clientSecret: string
  region: string
}

interface AuthTokens {
  accessToken: string
  idToken: string
  refreshToken: string
  expiresIn: number
}

class AuthService {
  private config: CognitoConfig | null = null
  private tokens: AuthTokens | null = null

  /**
   * 初始化Cognito配置
   */
  initialize(config: CognitoConfig) {
    this.config = config
    // 尝试从localStorage恢复token
    this.loadTokensFromStorage()
  }

  /**
   * 计算SECRET_HASH
   */
  private calculateSecretHash(username: string): string {
    if (!this.config) throw new Error('Auth service not initialized')
    
    const message = username + this.config.clientId
    const hash = CryptoJS.HmacSHA256(message, this.config.clientSecret)
    return CryptoJS.enc.Base64.stringify(hash)
  }

  /**
   * 用户登录
   */
  async login(username: string, password: string): Promise<AuthTokens> {
    if (!this.config) throw new Error('Auth service not initialized')
    
    // Web Client没有secret，不需要SECRET_HASH
    const authParameters: any = {
      USERNAME: username,
      PASSWORD: password,
    }
    
    // 只有当clientSecret存在时才计算SECRET_HASH
    if (this.config.clientSecret) {
      const secretHash = this.calculateSecretHash(username)
      authParameters.SECRET_HASH = secretHash
    }
    
    const endpoint = `https://cognito-idp.${this.config.region}.amazonaws.com/`
    
    const payload = {
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: this.config.clientId,
      AuthParameters: authParameters,
    }

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.message || error.__type || 'Login failed')
      }

      const data = await response.json()
      
      if (!data.AuthenticationResult) {
        throw new Error('Authentication failed')
      }

      this.tokens = {
        accessToken: data.AuthenticationResult.AccessToken,
        idToken: data.AuthenticationResult.IdToken,
        refreshToken: data.AuthenticationResult.RefreshToken,
        expiresIn: data.AuthenticationResult.ExpiresIn,
      }

      // 保存到localStorage
      this.saveTokensToStorage()

      return this.tokens
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  /**
   * 获取当前access token
   */
  getAccessToken(): string | null {
    return this.tokens?.accessToken || null
  }

  /**
   * 检查是否已登录
   */
  isAuthenticated(): boolean {
    return !!this.tokens?.accessToken
  }

  /**
   * 登出
   */
  logout() {
    this.tokens = null
    localStorage.removeItem('auth_tokens')
  }

  /**
   * 保存tokens到localStorage
   */
  private saveTokensToStorage() {
    if (this.tokens) {
      localStorage.setItem('auth_tokens', JSON.stringify(this.tokens))
    }
  }

  /**
   * 从localStorage加载tokens
   */
  private loadTokensFromStorage() {
    const stored = localStorage.getItem('auth_tokens')
    if (stored) {
      try {
        this.tokens = JSON.parse(stored)
      } catch (e) {
        console.error('Failed to parse stored tokens:', e)
      }
    }
  }

  /**
   * 刷新token（可选实现）
   */
  async refreshAccessToken(): Promise<void> {
    if (!this.config || !this.tokens?.refreshToken) {
      throw new Error('Cannot refresh token')
    }

    // TODO: 实现token刷新逻辑
    // 使用RefreshToken获取新的AccessToken
  }
}

export const authService = new AuthService()
export default authService
