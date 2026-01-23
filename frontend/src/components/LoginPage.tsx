/**
 * 登录页面组件
 * 使用Cloudscape Design System
 */

import React, { useState } from 'react'
import {
  Container,
  Header,
  FormField,
  Input,
  Button,
  SpaceBetween,
  Alert,
} from '@cloudscape-design/components'
import authService from '../services/authService'
import './LoginPage.css'

interface LoginPageProps {
  onLoginSuccess: () => void
}

const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('testuser@example.com')
  const [password, setPassword] = useState('MyPassword123!')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await authService.login(username, password)
      onLoginSuccess()
    } catch (err: any) {
      setError(err.message || '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-box">
        <Container
          header={
            <Header variant="h1">
              AgentCore 演示系统
            </Header>
          }
        >
          <form onSubmit={handleLogin}>
            <SpaceBetween size="l">
              {error && (
                <Alert type="error" dismissible onDismiss={() => setError(null)}>
                  {error}
                </Alert>
              )}

              <FormField label="用户名（邮箱）" description="默认测试账号: testuser@example.com">
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.detail.value)}
                  placeholder="输入邮箱地址"
                  disabled={loading}
                  autoComplete="username"
                />
              </FormField>

              <FormField label="密码" description="默认密码: MyPassword123!">
                <Input
                  value={password}
                  onChange={(e) => setPassword(e.detail.value)}
                  placeholder="输入密码"
                  type="password"
                  disabled={loading}
                  autoComplete="current-password"
                />
              </FormField>

              <Button
                variant="primary"
                loading={loading}
                fullWidth
                formAction="submit"
              >
                {loading ? '登录中...' : '登录'}
              </Button>

              <div className="login-info">
                <p>
                  <strong>测试账号信息：</strong>
                </p>
                <ul>
                  <li>用户名: testuser@example.com</li>
                  <li>密码: MyPassword123!</li>
                </ul>
                <p className="login-note">
                  💡 提示：Token有效期为2小时
                </p>
              </div>
            </SpaceBetween>
          </form>
        </Container>
      </div>
    </div>
  )
}

export default LoginPage
