import React, { useEffect, useCallback } from 'react'
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  Background,
  BackgroundVariant,
  ReactFlowProvider,
  useReactFlow
} from '@xyflow/react'
import { Container, Header, Button } from '@cloudscape-design/components'
import AgentNode from './nodes/AgentNode'
import ServiceNode from './nodes/ServiceNode'
import ToolNode from './nodes/ToolNode'
import { initialNodes, initialEdges } from '../config/workflowConfig'
import '@xyflow/react/dist/style.css'
import './WorkflowDiagram.css'

const nodeTypes = {
  agent: AgentNode,
  service: ServiceNode,
  tool: ToolNode,
}

interface WorkflowDiagramProps {
  activeNodes?: string[]
  traceEvents?: any[]
}

const WorkflowDiagramInner: React.FC<WorkflowDiagramProps> = ({ activeNodes = [], traceEvents = [] }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const { fitView } = useReactFlow()

  // Update nodes based on trace events
  useEffect(() => {
    if (traceEvents.length === 0) {
      // Reset all nodes to idle when no events
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          data: {
            ...node.data,
            status: 'idle',
            isActive: false,
            thinking: false,
          },
        }))
      )
      return
    }

    console.log('🔄 Processing trace events:', traceEvents)

    setNodes((nds) =>
      nds.map((node) => {
        // Find events for this node
        const nodeEvents = traceEvents.filter(e => e.data?.node_id === node.id)
        
        if (nodeEvents.length > 0) {
          const latestEvent = nodeEvents[nodeEvents.length - 1]
          const status = latestEvent.data?.status || 'processing'
          
          console.log(`  Node ${node.id}: status=${status}, events=${nodeEvents.length}`)
          
          return {
            ...node,
            data: {
              ...node.data,
              status: status,
              isActive: status === 'processing' || status === 'calling' || status === 'routing' || status === 'retrieving' || status === 'checking',
              thinking: node.type === 'agent' && status === 'thinking',
            },
          }
        }
        
        // Reset nodes that don't have events in current trace
        return {
          ...node,
          data: {
            ...node.data,
            status: 'idle',
            isActive: false,
            thinking: false,
          },
        }
      })
    )

    // Animate edges - only when BOTH source and target are active
    setEdges((eds) =>
      eds.map((edge) => {
        const sourceActive = activeNodes.includes(edge.source)
        const targetActive = activeNodes.includes(edge.target)
        const bothActive = sourceActive && targetActive
        
        return {
          ...edge,
          animated: bothActive,
          style: {
            ...edge.style,
            stroke: bothActive ? '#3b82f6' : sourceActive || targetActive ? '#60a5fa' : '#94a3b8',
            strokeWidth: bothActive ? 2 : 1,
          },
        }
      })
    )
  }, [traceEvents, activeNodes, setNodes, setEdges])

  // Fit view on mount
  useEffect(() => {
    setTimeout(() => fitView({ padding: 0.1 }), 100)
  }, [fitView])

  const handleReset = useCallback(() => {
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: {
          ...node.data,
          status: 'idle',
          isActive: false,
          thinking: false,
        },
      }))
    )
    setEdges((eds) =>
      eds.map((edge) => ({
        ...edge,
        animated: false,
        style: {
          ...edge.style,
          stroke: '#94a3b8',
          strokeWidth: 1,
        },
      }))
    )
  }, [setNodes, setEdges])

  return (
    <Container
      header={
        <Header
          variant="h2"
          actions={
            <Button onClick={handleReset} iconName="refresh">
              Reset
            </Button>
          }
        >
          Workflow Visualization
        </Header>
      }
    >
      <div style={{ width: '100%', height: 'calc(100vh - 180px)' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        </ReactFlow>
      </div>
    </Container>
  )
}

const WorkflowDiagram: React.FC<WorkflowDiagramProps> = (props) => {
  return (
    <ReactFlowProvider>
      <WorkflowDiagramInner {...props} />
    </ReactFlowProvider>
  )
}

export default WorkflowDiagram
