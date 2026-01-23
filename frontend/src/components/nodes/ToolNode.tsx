import React from 'react'
import { Handle, Position } from '@xyflow/react'

interface ToolNodeProps {
  data: {
    label: string
    description?: string
    status?: 'idle' | 'calling' | 'complete'
    width?: number
    height?: number
    clickUrl?: string
  }
}

const ToolNode: React.FC<ToolNodeProps> = ({ data }) => {
  const isActive = data.status === 'calling'
  const isComplete = data.status === 'complete'
  const width = data.width || 100
  const height = data.height || 70

  const handleClick = () => {
    if (data.clickUrl) {
      window.open(data.clickUrl, '_blank')
    }
  }

  return (
    <div
      onClick={handleClick}
      style={{
        background: isActive ? '#fbbf24' : isComplete ? '#10b981' : 'white',
        border: `2px solid ${isActive ? '#f59e0b' : isComplete ? '#059669' : '#d1d5db'}`,
        borderRadius: '8px',
        padding: '10px',
        minWidth: `${width}px`,
        minHeight: `${height}px`,
        width: `${width}px`,
        height: `${height}px`,
        textAlign: 'center',
        boxShadow: isActive ? '0 4px 12px rgba(245, 158, 11, 0.4)' : '0 2px 6px rgba(0,0,0,0.1)',
        transition: 'all 0.3s ease',
        transform: isActive ? 'scale(1.05)' : 'scale(1)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        cursor: data.clickUrl ? 'pointer' : 'default',
        position: 'relative',
      }}
    >
      {/* Dual handles - both source and target */}
      <Handle id="top" type="target" position={Position.Top} style={{ background: '#6b7280' }} />
      <Handle id="top" type="source" position={Position.Top} style={{ background: '#6b7280' }} />

      <div
        style={{
          fontWeight: 'bold',
          color: isActive || isComplete ? 'white' : '#333',
          fontSize: '12px',
          marginBottom: '2px',
        }}
      >
        {data.label}
      </div>
      <div
        style={{
          fontSize: '10px',
          color: isActive || isComplete ? 'rgba(255,255,255,0.9)' : '#666',
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
            color: isActive || isComplete ? 'white' : '#666',
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

export default ToolNode
