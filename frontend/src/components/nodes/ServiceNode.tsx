import React from 'react'
import { Handle, Position } from '@xyflow/react'

interface ServiceNodeProps {
  data: {
    label: string
    description?: string
    icon?: string
    color?: string
    status?: 'idle' | 'processing' | 'active' | 'complete'
    isActive?: boolean
    width?: number
    height?: number
    clickUrl?: string
  }
}

const ServiceNode: React.FC<ServiceNodeProps> = ({ data }) => {
  const isActive = data.isActive || data.status !== 'idle'
  const color = data.color || '#6b7280'
  const width = data.width || 110
  const height = data.height || 80

  const handleClick = () => {
    if (data.clickUrl) {
      window.open(data.clickUrl, '_blank')
    }
  }

  return (
    <div
      onClick={handleClick}
      style={{
        background: isActive ? `linear-gradient(135deg, ${color} 0%, ${color}dd 100%)` : 'white',
        border: `2px solid ${color}`,
        borderRadius: '12px',
        padding: '12px',
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
        cursor: data.clickUrl ? 'pointer' : 'default',
        position: 'relative',
      }}
    >
      {/* Dual handles - each position has both source and target */}
      <Handle id="top" type="target" position={Position.Top} style={{ background: color }} />
      <Handle id="top" type="source" position={Position.Top} style={{ background: color }} />
      
      <Handle id="bottom" type="target" position={Position.Bottom} style={{ background: color }} />
      <Handle id="bottom" type="source" position={Position.Bottom} style={{ background: color }} />
      
      <Handle id="left" type="target" position={Position.Left} style={{ background: color }} />
      <Handle id="left" type="source" position={Position.Left} style={{ background: color }} />
      
      <Handle id="right" type="target" position={Position.Right} style={{ background: color }} />
      <Handle id="right" type="source" position={Position.Right} style={{ background: color }} />

      <div style={{ fontSize: '24px', marginBottom: '6px' }}>
        {data.icon || '⚙️'}
      </div>
      <div
        style={{
          fontWeight: 'bold',
          color: isActive ? 'white' : '#333',
          fontSize: '13px',
          marginBottom: '3px',
        }}
      >
        {data.label}
      </div>
      <div
        style={{
          fontSize: '10px',
          color: isActive ? 'rgba(255,255,255,0.9)' : '#666',
        }}
      >
        {data.description}
      </div>
      {data.clickUrl && (
        <div
          style={{
            position: 'absolute',
            top: '4px',
            right: '4px',
            fontSize: '10px',
            color: isActive ? 'white' : color,
            opacity: 0.7,
          }}
          title="点击查看详情"
        >
          🔗
        </div>
      )}
    </div>
  )
}

export default ServiceNode
