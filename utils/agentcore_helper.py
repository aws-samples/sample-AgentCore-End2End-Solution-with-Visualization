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
    name, description, role_arn, client_id, discovery_url, lambda_arn, api_spec_file, region, web_client_id=None
):
    """创建AgentCore Gateway（支持多个allowed clients）"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # 准备allowed clients列表
    allowed_clients = [client_id]
    if web_client_id:
        allowed_clients.append(web_client_id)

    # 创建Gateway
    try:
        response = gateway_client.create_gateway(
            name=name,
            roleArn=role_arn,
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "allowedClients": allowed_clients,
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

            # 更新Gateway配置（roleArn、authorizerConfiguration可能因重新部署而变化）
            details = gateway_client.get_gateway(gatewayIdentifier=gateway_id)

            expected_authorizer = {
                "customJWTAuthorizer": {
                    "allowedClients": allowed_clients,
                    "discoveryUrl": discovery_url,
                }
            }

            needs_update = (
                details["roleArn"] != role_arn
                or details.get("authorizerConfiguration") != expected_authorizer
            )

            if needs_update:
                print(f"  🔧 更新Gateway配置（role/authorizer）...")
                update_params = {
                    "gatewayIdentifier": gateway_id,
                    "name": details["name"],
                    "roleArn": role_arn,
                    "protocolType": details["protocolType"],
                    "authorizerType": details["authorizerType"],
                    "authorizerConfiguration": expected_authorizer,
                }
                if "policyEngineConfiguration" in details:
                    update_params["policyEngineConfiguration"] = details["policyEngineConfiguration"]
                gateway_client.update_gateway(**update_params)
                # 等待Gateway更新和IAM角色传播
                import time
                time.sleep(10)
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


# ============================================================================
# Policy Engine Functions
# ============================================================================

def create_coupon_lambda(lambda_name, role_name, region):
    """创建CouponTool Lambda函数和IAM Role"""
    import zipfile
    import io
    
    iam_client = boto3.client("iam", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)
    
    # 1. 创建Lambda Role
    try:
        with open("lambda/trust_policy_coupon.json", "r") as f:
            trust_policy = f.read()
        
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy,
            Description="IAM Role for CouponTool Lambda function"
        )
        role_arn = response["Role"]["Arn"]
        
        # 附加基本执行策略
        with open("lambda/iam_policy_coupon.json", "r") as f:
            policy_document = f.read()
        
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="LambdaBasicExecution",
            PolicyDocument=policy_document
        )
        
        # 等待Role生效
        time.sleep(10)
        
    except iam_client.exceptions.EntityAlreadyExistsException:
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response["Role"]["Arn"]
    
    # 2. 创建Lambda函数
    try:
        # 创建ZIP包
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write("lambda/lambda_coupon.py", "lambda_function.py")
        
        zip_buffer.seek(0)
        
        # 创建Lambda函数
        response = lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": zip_buffer.read()},
            Description="代金券批复工具Lambda函数",
            Timeout=30,
            MemorySize=128
        )
        
        lambda_arn = response["FunctionArn"]
        
        # 等待函数激活
        waiter = lambda_client.get_waiter("function_active")
        waiter.wait(FunctionName=lambda_name)
        
    except lambda_client.exceptions.ResourceConflictException:
        response = lambda_client.get_function(FunctionName=lambda_name)
        lambda_arn = response["Configuration"]["FunctionArn"]
    
    return lambda_arn, role_arn


def add_coupon_gateway_target(gateway_id, target_name, lambda_arn, region):
    """添加CouponTool Target到Gateway"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    # 检查Target是否已存在
    try:
        response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for target in response.get("items", []):
            if target.get("name") == target_name:
                return target.get("targetId")
    except Exception:
        pass
    
    # 加载API spec
    with open("lambda/api_spec_coupon.json", "r") as f:
        api_spec = json.load(f)
    
    # 创建Target
    response = gateway_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=target_name,
        description="代金券批复工具Target",
        targetConfiguration={
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {"inlinePayload": api_spec}
                }
            }
        },
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ]
    )
    
    return response["targetId"]


def create_policy_engine(engine_name, region):
    """创建Policy Engine"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    # 检查是否已存在
    try:
        response = gateway_client.list_policy_engines()
        for pe in response.get("policyEngines", []):
            if pe.get("name") == engine_name:
                return pe.get("policyEngineId")
    except Exception:
        pass
    
    # 创建Policy Engine
    response = gateway_client.create_policy_engine(
        name=engine_name,
        description="Customer Support Gateway Policy Engine - 控制工具访问权限"
    )
    
    policy_engine_id = response["policyEngineId"]
    
    # 等待创建完成
    time.sleep(5)
    
    return policy_engine_id


def create_policy_rules(policy_engine_id, gateway_arn, region):
    """创建Policy规则（4个Cedar规则）"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    # 定义4个Policy规则
    policies = [
        {
            "name": "AllowCheckWarranty",
            "description": "允许check_warranty_status工具",
            "statement": f"""permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"LambdaTools___check_warranty_status",
    resource == AgentCore::Gateway::"{gateway_arn}"
);"""
        },
        {
            "name": "AllowWebSearch",
            "description": "允许web_search工具",
            "statement": f"""permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"LambdaTools___web_search",
    resource == AgentCore::Gateway::"{gateway_arn}"
);"""
        },
        {
            "name": "AllowCouponUnder500",
            "description": "允许金额<500的代金券",
            "statement": f"""permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"CouponToolTarget___CouponTool",
    resource == AgentCore::Gateway::"{gateway_arn}"
) when {{
    context.input.amount < 500
}};"""
        },
        {
            "name": "DenyCouponOver500",
            "description": "拒绝金额>=500的代金券",
            "statement": f"""forbid(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"CouponToolTarget___CouponTool",
    resource == AgentCore::Gateway::"{gateway_arn}"
) when {{
    context.input.amount >= 500
}};"""
        }
    ]
    
    created_policies = []
    
    for policy in policies:
        try:
            response = gateway_client.create_policy(
                name=f"CustomerSupport_{policy['name']}",
                definition={
                    "cedar": {
                        "statement": policy["statement"]
                    }
                },
                description=policy["description"],
                policyEngineId=policy_engine_id,
                validationMode="IGNORE_ALL_FINDINGS"
            )
            
            created_policies.append(response["policyId"])
            
        except Exception as e:
            # Policy可能已存在
            if "already exists" not in str(e).lower():
                print(f"Warning: Failed to create policy {policy['name']}: {e}")
    
    return created_policies


def attach_policy_to_gateway(gateway_id, policy_engine_id, mode, region):
    """将Policy Engine关联到Gateway"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    # 获取Policy Engine ARN
    pe_response = gateway_client.get_policy_engine(policyEngineId=policy_engine_id)
    policy_engine_arn = pe_response["policyEngineArn"]
    
    # 获取当前Gateway配置
    gateway_info = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
    
    # 更新Gateway，添加Policy Engine配置
    update_params = {
        "gatewayIdentifier": gateway_id,
        "name": gateway_info["name"],
        "roleArn": gateway_info["roleArn"],
        "protocolType": gateway_info["protocolType"],
        "authorizerType": gateway_info["authorizerType"],
        "policyEngineConfiguration": {
            "arn": policy_engine_arn,
            "mode": mode
        }
    }
    
    # 如果有authorizerConfiguration，也要包含
    if "authorizerConfiguration" in gateway_info:
        update_params["authorizerConfiguration"] = gateway_info["authorizerConfiguration"]
    
    gateway_client.update_gateway(**update_params)


def update_gateway_role_for_policy(gateway_role_arn, coupon_lambda_arn, region):
    """更新Gateway Role权限（添加Policy评估权限和Coupon Lambda调用权限）"""
    iam_client = boto3.client("iam", region_name=region)
    role_name = gateway_role_arn.split("/")[-1]
    
    # 1. 添加Policy Engine权限（使用通配符确保成功）
    try:
        policy_engine_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "bedrock-agentcore:*",
                    "Resource": "*"
                }
            ]
        }
        
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="PolicyEngineAccess",
            PolicyDocument=json.dumps(policy_engine_policy)
        )
    except Exception:
        pass
    
    # 2. 更新Lambda调用权限（添加Coupon Lambda）
    try:
        # 获取现有的BedrockAgentPolicy
        existing_policy = iam_client.get_role_policy(
            RoleName=role_name,
            PolicyName="BedrockAgentPolicy"
        )
        
        policy_doc = json.loads(existing_policy["PolicyDocument"]) if isinstance(existing_policy["PolicyDocument"], str) else existing_policy["PolicyDocument"]
        
        # 添加Coupon Lambda ARN到Resource列表
        for statement in policy_doc["Statement"]:
            if statement.get("Action") == ["lambda:InvokeFunction"]:
                if coupon_lambda_arn not in statement["Resource"]:
                    if isinstance(statement["Resource"], list):
                        statement["Resource"].append(coupon_lambda_arn)
                    else:
                        statement["Resource"] = [statement["Resource"], coupon_lambda_arn]
        
        # 更新策略
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockAgentPolicy",
            PolicyDocument=json.dumps(policy_doc)
        )
    except Exception:
        pass


def delete_policy_engine(policy_engine_id, region):
    """删除Policy Engine及其所有规则"""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
    
    try:
        # 先删除所有policies
        response = gateway_client.list_policies(policyEngineId=policy_engine_id)
        for policy in response.get("policies", []):
            try:
                gateway_client.delete_policy(
                    policyEngineId=policy_engine_id,
                    policyId=policy["policyId"]
                )
            except Exception:
                pass
        
        # 删除Policy Engine
        gateway_client.delete_policy_engine(policyEngineId=policy_engine_id)
    except Exception:
        pass


def delete_coupon_lambda(lambda_name, role_name, region):
    """删除CouponTool Lambda函数和IAM Role"""
    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)
    
    # 删除Lambda函数
    try:
        lambda_client.delete_function(FunctionName=lambda_name)
    except Exception:
        pass
    
    # 删除IAM Role
    try:
        # 先删除内联策略
        try:
            iam_client.delete_role_policy(
                RoleName=role_name,
                PolicyName="LambdaBasicExecution"
            )
        except Exception:
            pass
        
        # 删除Role
        iam_client.delete_role(RoleName=role_name)
    except Exception:
        pass
