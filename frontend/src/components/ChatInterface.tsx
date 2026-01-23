import React, { useState, useRef, useEffect } from 'react'
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  Input,
  Box,
  Spinner
} from '@cloudscape-design/components'
import { invokeAgent } from '../services/agentService'
import './ChatInterface.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface ChatInterfaceProps {
  onTraceEvents: (events: any[]) => void
}

// Simple markdown formatter
const formatMarkdown = (text: string): string => {
  return text
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Bullet points
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Wrap lists
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    // Line breaks
    .replace(/\n/g, '<br/>')
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ onTraceEvents }) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await invokeAgent(input)
      
      console.log('📦 Agent response:', response)
      
      // Pass trace events to parent
      if (response.events) {
        console.log('✅ Found events:', response.events.length)
        onTraceEvents(response.events)
      } else {
        console.log('❌ No events in response')
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.response || 'No response received',
        timestamp: new Date()
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error invoking agent:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (event: any) => {
    const e = event.detail as KeyboardEvent
    if (e.key === 'Enter' && !e.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <Container
      header={
        <Header variant="h2">
          Customer Support Chat
        </Header>
      }
    >
      <div style={{ 
        height: 'calc(100vh - 180px)', 
        display: 'flex', 
        flexDirection: 'column',
      }}>
        <div className="chat-messages" style={{ flex: 1, overflowY: 'auto' }}>
          {messages.length === 0 && (
            <Box textAlign="center" color="text-body-secondary" padding="xxl">
              Start a conversation with the customer support agent
            </Box>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className={`message message-${msg.role}`}>
              <div className="message-header">
                <strong>{msg.role === 'user' ? 'You' : 'Agent'}</strong>
                <span className="message-time">
                  {msg.timestamp.toLocaleTimeString()}
                </span>
              </div>
              <div className="message-content">
        <div dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }} />
      </div>
            </div>
          ))}
          {loading && (
            <div className="message message-assistant">
              <div className="message-header">
                <strong>Agent</strong>
              </div>
              <div className="message-content">
                <Spinner /> Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input" style={{ flexShrink: 0, paddingTop: '12px' }}>
          <SpaceBetween direction="horizontal" size="xs">
            <Input
              value={input}
              onChange={({ detail }) => setInput(detail.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your message..."
              disabled={loading}
              className="chat-input-field"
            />
            <Button
              variant="primary"
              onClick={handleSend}
              disabled={loading || !input.trim()}
            >
              Send
            </Button>
          </SpaceBetween>
        </div>
      </div>
    </Container>
  )
}

export default ChatInterface
