"""
AgentCore资源创建和管理辅助函数
"""

import time
import json
import boto3
from pathlib import Path
from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager
from bedrock_agentcore.memory.constants import StrategyType
from bedrock_agentcore_starter_toolkit import Runtime


def put_ssm_parameter(name, value):
    """保存SSM参数"""
    ssm = boto3.client("ssm")
    ssm.put_parameter(
        Name=name,
        Value=value,
        Type="String",
        Overwrite=True
    )


def get_ssm_parameter(name):
    """获取SSM参数"""
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]


def create_agentcore_memory(name, description, region):
    """创建AgentCore Memory"""
    memory_manager = MemoryManager(region_name=region)

    memory = memory_manager.get_or_create_memory(
        name=name,
        strategies=[
            {
                StrategyType.USER_PREFERENCE.value: {
                    "name": "CustomerPreferences",
                    "description": "Captures customer preferences and behavior",
                    "namespaces": ["support/customer/{actorId}/preferences"],
                }
            },
            {
                StrategyType.SEMANTIC.value: {
                    "name": "CustomerSupportSemantic",
                    "description": "Stores facts from conversations",
                    "namespaces": ["support/customer/{actorId}/semantic"],
                }
            },
        ],
    )

    return memory["id"]


def create_agentcore_gateway(
    name, description, role_arn, client_id, discovery_url, lambda_arn, api_spec_file, region
):
    """创建AgentCore Gateway"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # 创建Gateway
    try:
        response = gateway_client.create_gateway(
            name=name,
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "allowedClients": [client_id],
                    "discoveryUrl": discovery_url,
                }
            },
            description=description,
        )
        gateway_id = response["gatewayId"]
    except Exception as e:
        if "already exists" in str(e).lower():
            # Gateway已存在，获取ID
            gateways = gateway_client.list_gateways()
            for gw in gateways.get("items", []):
                if gw["name"] == name:
                    gateway_id = gw["gatewayId"]
                    break
        else:
            raise

    # 保存gateway_id到SSM（与lab-06一致）
    put_ssm_parameter("/app/customersupport/agentcore/gateway_id", gateway_id)

    # 加载API spec
    with open(api_spec_file, "r") as f:
        api_spec = json.load(f)

    # 添加Lambda Target
    try:
        gateway_client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name="LambdaTools",
            description="Lambda tools for customer support",
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {"inlinePayload": api_spec},
                    }
                }
            },
            credentialProviderConfigurations=[
                {"credentialProviderType": "GATEWAY_IAM_ROLE"}
            ],
        )
    except Exception:
        # Target可能已存在
        pass

    return gateway_id


def deploy_agentcore_runtime(
    entrypoint,
    requirements_file,
    execution_role,
    agent_name,
    client_id,
    discovery_url,
    memory_id,
    region,
    web_client_id=None,
):
    """部署AgentCore Runtime"""
    runtime = Runtime()

    # 准备allowed clients列表
    allowed_clients = [client_id]
    if web_client_id:
        allowed_clients.append(web_client_id)

    # 配置Runtime
    runtime.configure(
        entrypoint=entrypoint,
        execution_role=execution_role,
        auto_create_ecr=True,
        requirements_file=requirements_file,
        region=region,
        agent_name=agent_name,
        authorizer_configuration={
            "customJWTAuthorizer": {
                "allowedClients": allowed_clients,
                "discoveryUrl": discovery_url,
            }
        },
        request_header_configuration={
            "requestHeaderAllowlist": [
                "Authorization",
                "X-Amzn-Bedrock-AgentCore-Runtime-Custom-H1",
            ]
        },
    )

    # 部署Runtime
    launch_result = runtime.launch(
        env_vars={"MEMORY_ID": memory_id},
        auto_update_on_conflict=True,
    )

    return launch_result.agent_arn


def wait_for_runtime_ready(agent_name, max_wait=600):
    """等待Runtime就绪"""
    control_client = boto3.client("bedrock-agentcore-control")
    start_time = time.time()
    
    # 获取runtime列表
    while time.time() - start_time < max_wait:
        try:
            runtimes = control_client.list_agent_runtimes()
            for runtime in runtimes.get("agentRuntimes", []):
                if agent_name in runtime.get("agentRuntimeId", ""):
                    runtime_id = runtime["agentRuntimeId"]
                    
                    # 获取runtime详情
                    detail = control_client.get_agent_runtime(agentRuntimeId=runtime_id)
                    status = detail["agentRuntime"]["status"]
                    
                    if status == "ACTIVE":
                        return True
                    elif status in ["CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"]:
                        raise Exception(f"Runtime failed with status: {status}")
            
            time.sleep(10)
        except Exception as e:
            if "not found" in str(e).lower():
                time.sleep(10)
                continue
            raise

    raise TimeoutError("Runtime did not become ready within timeout period")


def delete_agentcore_memory(memory_id):
    """删除AgentCore Memory"""
    control_client = boto3.client("bedrock-agentcore-control")
    try:
        control_client.delete_memory(memoryId=memory_id)
    except Exception:
        pass


def delete_agentcore_gateway(gateway_id):
    """删除AgentCore Gateway"""
    gateway_client = boto3.client("bedrock-agentcore-control")

    try:
        # 先删除所有targets
        targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for target in targets.get("items", []):
            gateway_client.delete_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target["targetId"],
            )

        # 删除Gateway
        gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
    except Exception:
        pass


def delete_agentcore_runtime(runtime_arn):
    """删除AgentCore Runtime"""
    control_client = boto3.client("bedrock-agentcore-control")

    try:
        # 提取runtime ID
        runtime_id = runtime_arn.split(":")[-1].split("/")[-1]
        control_client.delete_agent_runtime(agentRuntimeId=runtime_id)

        # 等待删除完成
        time.sleep(30)
    except Exception:
        pass

    # 删除ECR repository
    try:
        ecr_client = boto3.client("ecr")
        repositories = ecr_client.describe_repositories()
        for repo in repositories["repositories"]:
            if "bedrock-agentcore" in repo["repositoryName"]:
                ecr_client.delete_repository(
                    repositoryName=repo["repositoryName"],
                    force=True,
                )
    except Exception:
        pass
