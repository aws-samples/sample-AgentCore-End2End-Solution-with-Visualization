import React from 'react'
import { Handle, Position } from '@xyflow/react'

interface AgentNodeProps {
  data: {
    label: string
    description?: string
    icon?: string
    color?: string
    status?: 'idle' | 'thinking' | 'processing' | 'complete'
    thinking?: boolean
    width?: number
    height?: number
  }
}

const AgentNode: React.FC<AgentNodeProps> = ({ data }) => {
  const isActive = data.status !== 'idle'
  const color = data.color || '#3b82f6'
  const width = data.width || 140
  const height = data.height || 100

  return (
    <div
      style={{
        background: isActive ? `linear-gradient(135deg, ${color} 0%, ${color}dd 100%)` : 'white',
        border: `2px solid ${color}`,
        borderRadius: '16px',
        padding: '16px',
        minWidth: `${width}px`,
        minHeight: `${height}px`,
        width: `${width}px`,
        height: `${height}px`,
        textAlign: 'center',
        boxShadow: isActive ? `0 6px 24px ${color}40` : '0 3px 10px rgba(0,0,0,0.1)',
        transition: 'all 0.4s ease',
        transform: isActive ? 'scale(1.05)' : 'scale(1)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      {/* Handles with proper source/target types */}
      <Handle id="top" type="target" position={Position.Top} style={{ background: color }} />
      <Handle id="bottom" type="source" position={Position.Bottom} style={{ background: color }} />
      <Handle id="left" type="source" position={Position.Left} style={{ background: color }} />
      <Handle id="right" type="source" position={Position.Right} style={{ background: color }} />
      
      {/* Additional handles for reverse connections (invisible) */}
      <Handle id="top-source" type="source" position={Position.Top} style={{ background: color, opacity: 0, pointerEvents: 'none' }} />
      <Handle id="bottom-target" type="target" position={Position.Bottom} style={{ background: color, opacity: 0, pointerEvents: 'none' }} />
      <Handle id="left-target" type="target" position={Position.Left} style={{ background: color, opacity: 0, pointerEvents: 'none' }} />
      <Handle id="right-target" type="target" position={Position.Right} style={{ background: color, opacity: 0, pointerEvents: 'none' }} />

      <div style={{ fontSize: '32px', marginBottom: '8px' }}>
        {data.icon || '🤖'}
      </div>
      <div
        style={{
          fontWeight: 'bold',
          color: isActive ? 'white' : '#333',
          fontSize: '14px',
          marginBottom: '4px',
        }}
      >
        {data.label}
      </div>
      <div
        style={{
          fontSize: '11px',
          color: isActive ? 'rgba(255,255,255,0.9)' : '#666',
        }}
      >
        {data.description}
      </div>
      {data.thinking && (
        <div
          style={{
            marginTop: '8px',
            fontSize: '10px',
            color: 'white',
            animation: 'pulse 1.5s infinite',
          }}
        >
          Thinking...
        </div>
      )}
    </div>
  )
}

export default AgentNode
