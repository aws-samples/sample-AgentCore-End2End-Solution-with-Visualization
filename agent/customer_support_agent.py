"""
Customer Support Agent - 整合Lab 1-6的完整Agent实现
支持Memory、Gateway、Runtime + Streaming可视化
基于lab4_runtime_streaming.py
"""

import os
import json
import asyncio
import uuid
import boto3
from typing import AsyncGenerator, Dict, Any
from datetime import datetime
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from strands.tools import tool
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

# 导入本地工具
from agent.tools import get_product_info, get_return_policy, get_technical_support, SYSTEM_PROMPT

# 初始化
REGION = boto3.Session().region_name
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# 获取Memory ID from环境变量
MEMORY_ID = os.environ.get("MEMORY_ID")
if not MEMORY_ID:
    raise Exception("Environment variable MEMORY_ID is required")

# 初始化Bedrock模型
model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

# 初始化AgentCore Runtime App
app = BedrockAgentCoreApp()


async def emit_event(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """创建trace事件用于前端可视化"""
    return {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data
    }


def create_gateway_tools(mcp_client):
    """创建Gateway工具的包装函数（规避list_tools_sync权限问题）"""
    
    @tool
    def check_warranty_status(serial_number: str, customer_email: str = None) -> str:
        """Check the warranty status of a product using its serial number"""
        result = mcp_client.call_tool_sync(
            tool_use_id=str(uuid.uuid4()),
            name="LambdaTools___check_warranty_status",
            arguments={"serial_number": serial_number, "customer_email": customer_email}
        )
        return str(result)
    
    @tool
    def web_search(keywords: str, region: str = "us-en", max_results: int = 5) -> str:
        """Search the web for updated information"""
        result = mcp_client.call_tool_sync(
            tool_use_id=str(uuid.uuid4()),
            name="LambdaTools___web_search",
            arguments={"keywords": keywords, "region": region, "max_results": max_results}
        )
        return str(result)
    
    @tool
    def CouponTool(amount: int) -> str:
        """批复代金券给客户。金额必须是整数（美元）。"""
        result = mcp_client.call_tool_sync(
            tool_use_id=str(uuid.uuid4()),
            name="CouponToolTarget___CouponTool",
            arguments={"amount": amount}
        )
        return str(result)
    
    return [check_warranty_status, web_search, CouponTool]


class TracingAgent:
    """Agent包装器，用于捕获工具调用并生成trace事件"""
    
    def __init__(self, agent: Agent):
        self.agent = agent
    
    async def invoke_with_tracing(self, user_input: str) -> AsyncGenerator[Dict[str, Any], None]:
        """调用agent并生成trace事件"""
        import io
        import sys
        
        # 发送用户输入事件
        yield await emit_event("user_input", {
            "node_id": "user",
            "message": user_input
        })
        
        # Runtime开始
        yield await emit_event("runtime_start", {
            "node_id": "runtime",
            "status": "processing"
        })
        
        # Agent开始思考
        yield await emit_event("agent_start", {
            "node_id": "agent",
            "status": "thinking"
        })
        
        # Memory检索
        yield await emit_event("memory_access", {
            "node_id": "memory",
            "action": "retrieving",
            "status": "processing"
        })
        
        try:
            # 捕获stdout来检测工具调用
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            try:
                response = self.agent(user_input)
            finally:
                sys.stdout = old_stdout
                output = captured_output.getvalue()
            
            # 解析工具调用
            tool_calls_detected = []
            for line in output.split('\n'):
                if line.startswith('Tool #'):
                    parts = line.split(': ', 1)
                    if len(parts) == 2:
                        tool_name = parts[1].strip()
                        tool_calls_detected.append(tool_name)
            
            # 工具节点映射
            tool_node_map = {
                "get_product_info": "tool-product",
                "get_return_policy": "tool-return",
                "get_technical_support": "tool-kb",
                "web_search": "tool-websearch",
                "check_warranty_status": "tool-warranty",
                "CouponTool": "tool-coupon",
            }
            
            # 发送工具调用事件
            for tool_name in tool_calls_detected:
                # Gateway路由
                yield await emit_event("gateway_routing", {
                    "node_id": "gateway",
                    "tool": tool_name,
                    "status": "routing"
                })
                
                # Lambda工具需要policy检查
                if tool_name in ["web_search", "check_warranty_status", "CouponTool"]:
                    yield await emit_event("policy_check", {
                        "node_id": "policy",
                        "tool": tool_name,
                        "status": "checking"
                    })
                
                tool_node = tool_node_map.get(tool_name, "tool-unknown")
                
                # 工具调用
                yield await emit_event("tool_call", {
                    "node_id": tool_node,
                    "tool_name": tool_name,
                    "status": "calling"
                })
                
                await asyncio.sleep(0.3)
                
                # 工具结果
                yield await emit_event("tool_result", {
                    "node_id": tool_node,
                    "tool_name": tool_name,
                    "status": "complete"
                })
            
            # Observability日志
            yield await emit_event("observability", {
                "node_id": "observability",
                "status": "logging"
            })
            
            # 提取最终响应
            final_text = ""
            if hasattr(response, 'message') and 'content' in response.message:
                for content_block in response.message['content']:
                    if isinstance(content_block, dict) and 'text' in content_block:
                        final_text = content_block['text']
                        break
            
            # Agent完成
            yield await emit_event("agent_complete", {
                "node_id": "agent",
                "status": "complete",
                "response": final_text
            })
            
            # 最终响应
            yield await emit_event("response", {
                "node_id": "runtime",
                "content": final_text,
                "status": "complete"
            })
            
        except Exception as e:
            yield await emit_event("error", {
                "node_id": "agent",
                "error": str(e),
                "status": "error"
            })


@app.entrypoint
async def invoke(payload, context=None):
    """AgentCore Runtime entrypoint with streaming support"""
    
    user_input = payload.get("prompt", "")
    
    # 获取请求头（用户的Web Client token）
    request_headers = context.request_headers or {}
    user_auth_header = request_headers.get("Authorization", "")
    
    if not user_auth_header:
        return {"error": "Missing Authorization header"}
    
    # 获取Gateway配置
    ssm = boto3.client("ssm")
    try:
        # 使用与lab-06一致的SSM参数名
        gateway_id = ssm.get_parameter(
            Name="/app/customersupport/agentcore/gateway_id"
        )["Parameter"]["Value"]
    except Exception as e:
        return {"error": f"Gateway not configured: {str(e)}"}
    
    # 获取Gateway URL
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    gateway_response = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
    gateway_url = gateway_response["gatewayUrl"]
    
    # 获取Machine Client token用于Gateway调用
    # Runtime需要使用自己的身份（Machine Client）来调用Gateway
    try:
        # 从SSM获取Machine Client配置
        machine_client_id = ssm.get_parameter(
            Name="/app/customersupport/agentcore/client_id"
        )["Parameter"]["Value"]
        
        machine_client_secret = ssm.get_parameter(
            Name="/app/customersupport/agentcore/client_secret"
        )["Parameter"]["Value"]
        
        # 获取token endpoint
        token_url = ssm.get_parameter(
            Name="/app/customersupport/agentcore/cognito_token_url"
        )["Parameter"]["Value"]
        
        # 使用OAuth2 Client Credentials流程
        import base64
        credentials = base64.b64encode(f"{machine_client_id}:{machine_client_secret}".encode()).decode()
        
        import httpx
        token_response = httpx.post(
            token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {credentials}"
            },
            data={
                "grant_type": "client_credentials",
                "scope": ssm.get_parameter(Name="/app/customersupport/agentcore/cognito_auth_scope")["Parameter"]["Value"]
            },
            timeout=10.0
        )
        
        if token_response.status_code == 200:
            machine_token = token_response.json()["access_token"]
            gateway_auth_header = f"Bearer {machine_token}"
        else:
            print(f"[Warning] Failed to get machine token: {token_response.text}")
            gateway_auth_header = user_auth_header
        
    except Exception as e:
        print(f"[Warning] Failed to get machine token, using user token: {e}")
        # Fallback: 使用用户token
        gateway_auth_header = user_auth_header
    
    # 配置Memory
    session_id = str(uuid.uuid4())
    actor_id = "customer_001"
    
    memory_config = AgentCoreMemoryConfig(
        memory_id=MEMORY_ID,
        session_id=session_id,
        actor_id=actor_id,
        retrieval_config={
            "support/customer/{actorId}/semantic": RetrievalConfig(
                top_k=3, relevance_score=0.2
            ),
            "support/customer/{actorId}/preferences": RetrievalConfig(
                top_k=3, relevance_score=0.2
            ),
        },
    )
    
    try:
        # 创建MCP客户端（使用Machine Client token）
        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=gateway_url, headers={"Authorization": gateway_auth_header}
            )
        )
        
        with mcp_client:
            # 创建工具（本地 + Gateway）
            gateway_tools = create_gateway_tools(mcp_client)
            tools = [
                get_product_info,
                get_return_policy,
                get_technical_support,
            ] + gateway_tools
            
            # 创建Agent
            agent = Agent(
                model=model,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
                session_manager=AgentCoreMemorySessionManager(memory_config, REGION),
            )
            
            # 创建tracing包装器
            tracing_agent = TracingAgent(agent)
            
            # 收集所有事件
            events = []
            async for event in tracing_agent.invoke_with_tracing(user_input):
                events.append(event)
            
            # 提取最终响应
            final_response = ""
            for event in events:
                if event['type'] == 'response':
                    final_response = event['data'].get('content', '')
            
            # 返回响应和事件（用于前端可视化）
            return {
                "response": final_response,
                "events": events,
                "streaming": True
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "events": [{
                "type": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"error": str(e)}
            }]
        }


if __name__ == "__main__":
    app.run()
