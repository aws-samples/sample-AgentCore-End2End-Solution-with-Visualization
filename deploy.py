#!/usr/bin/env python3
"""
AgentCore E2E 可视化演示 - AgentCore资源部署脚本

前置条件：必须先运行 ./prereq.sh 创建基础资源

这个脚本会自动部署AgentCore相关资源：
- AgentCore Memory
- AgentCore Gateway  
- AgentCore Runtime
- React前端应用
"""

import os
import sys
import json
import yaml
import time
import boto3
import base64
import hashlib
import hmac
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# 添加utils到路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.agentcore_helper import (
    create_agentcore_memory,
    create_agentcore_gateway,
    deploy_agentcore_runtime,
    wait_for_runtime_ready,
    put_ssm_parameter,
    get_ssm_parameter,
    create_coupon_lambda,
    add_coupon_gateway_target,
    create_policy_engine,
    create_policy_rules,
    attach_policy_to_gateway,
    update_gateway_role_for_policy,
)
from utils.aws_helper import (
    create_s3_website_bucket,
    create_cloudfront_distribution,
    upload_directory,
)

console = Console()


class AgentCoreDeployer:
    """AgentCore部署器（仅AgentCore资源）"""

    def __init__(self, config_file="config.yaml"):
        """初始化部署器"""
        self.config = self.load_config(config_file)
        self.session = boto3.Session()
        self.region = self.config.get("project", {}).get("region") or self.session.region_name
        self.account_id = boto3.client("sts").get_caller_identity()["Account"]
        self.resources = {}
        self.deployment_file = "deployment_info.yaml"

    def load_config(self, config_file):
        """加载配置文件"""
        with open(config_file, "r") as f:
            return yaml.safe_load(f)

    def save_resources(self):
        """保存资源信息"""
        with open(self.deployment_file, "w") as f:
            yaml.dump(self.resources, f, default_flow_style=False)

    def check_prerequisites(self):
        """检查prereq.sh是否已运行"""
        console.print("\n[bold cyan]检查前置条件...[/bold cyan]")
        
        required_params = [
            "/app/customersupport/agentcore/pool_id",
            "/app/customersupport/agentcore/client_id",
            "/app/customersupport/agentcore/cognito_discovery_url",
            "/app/customersupport/agentcore/gateway_iam_role",
            "/app/customersupport/agentcore/lambda_arn",
        ]
        
        missing = []
        for param in required_params:
            try:
                get_ssm_parameter(param)
            except Exception:
                missing.append(param)
        
        if missing:
            console.print("[bold red]❌ 缺少前置资源！[/bold red]")
            console.print("\n[yellow]请先运行以下命令创建基础资源：[/yellow]")
            console.print("[cyan]  bash prereq.sh[/cyan]\n")
            console.print("[dim]缺少的SSM参数：[/dim]")
            for param in missing:
                console.print(f"  • {param}")
            sys.exit(1)
        
        console.print("  ✅ 前置资源已就绪")

    def load_existing_resources(self):
        """从SSM加载现有资源"""
        console.print("\n[bold cyan]加载现有资源...[/bold cyan]")
        
        try:
            self.resources["cognito"] = {
                "pool_id": get_ssm_parameter("/app/customersupport/agentcore/pool_id"),
                "client_id": get_ssm_parameter("/app/customersupport/agentcore/client_id"),  # Machine client (for Gateway)
                "web_client_id": get_ssm_parameter("/app/customersupport/agentcore/web_client_id"),  # Web client (for frontend)
                "discovery_url": get_ssm_parameter("/app/customersupport/agentcore/cognito_discovery_url"),
            }
            
            # 获取Machine client secret（用于Gateway）
            cognito = boto3.client("cognito-idp", region_name=self.region)
            machine_client_response = cognito.describe_user_pool_client(
                UserPoolId=self.resources["cognito"]["pool_id"],
                ClientId=self.resources["cognito"]["client_id"]
            )
            self.resources["cognito"]["client_secret"] = machine_client_response["UserPoolClient"].get("ClientSecret", "")
            
            # 保存client_secret到SSM（始终同步最新值）
            if self.resources["cognito"]["client_secret"]:
                try:
                    existing_secret = get_ssm_parameter("/app/customersupport/agentcore/client_secret")
                except Exception:
                    existing_secret = None
                if existing_secret != self.resources["cognito"]["client_secret"]:
                    put_ssm_parameter("/app/customersupport/agentcore/client_secret", self.resources["cognito"]["client_secret"])
                    console.print("  ✅ Machine Client Secret已同步到SSM")
            
            # 获取Web client secret（用于前端登录）
            web_client_response = cognito.describe_user_pool_client(
                UserPoolId=self.resources["cognito"]["pool_id"],
                ClientId=self.resources["cognito"]["web_client_id"]
            )
            self.resources["cognito"]["web_client_secret"] = web_client_response["UserPoolClient"].get("ClientSecret", "")
            
            # 确保Web Client启用USER_PASSWORD_AUTH
            console.print("  🔧 配置Web Client...")
            explicit_auth_flows = web_client_response["UserPoolClient"].get("ExplicitAuthFlows", [])
            if "ALLOW_USER_PASSWORD_AUTH" not in explicit_auth_flows:
                console.print("  ⚙️  启用USER_PASSWORD_AUTH...")
                # update_user_pool_client 是全量更新，必须保留原有配置
                update_params = {
                    "UserPoolId": self.resources["cognito"]["pool_id"],
                    "ClientId": self.resources["cognito"]["web_client_id"],
                    "ExplicitAuthFlows": list(set(explicit_auth_flows + ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"])),
                }
                # 保留原有的 OAuth 配置
                for key in ["AllowedOAuthFlows", "AllowedOAuthScopes", "CallbackURLs", "LogoutURLs",
                             "SupportedIdentityProviders", "AllowedOAuthFlowsUserPoolClient",
                             "AccessTokenValidity", "IdTokenValidity", "RefreshTokenValidity",
                             "TokenValidityUnits", "EnableTokenRevocation"]:
                    if key in web_client_response["UserPoolClient"] and web_client_response["UserPoolClient"][key] is not None:
                        update_params[key] = web_client_response["UserPoolClient"][key]
                cognito.update_user_pool_client(**update_params)
            
            # 创建测试用户（如果不存在）
            console.print("  👤 检查测试用户...")
            self.ensure_test_user()
            
            # 获取bearer token（使用Machine client）
            self.resources["cognito"]["bearer_token"] = self.get_cognito_token()
            
            self.resources["gateway_role_arn"] = get_ssm_parameter("/app/customersupport/agentcore/gateway_iam_role")
            self.resources["runtime_role_arn"] = get_ssm_parameter("/app/customersupport/agentcore/runtime_iam_role")
            self.resources["lambda_arn"] = get_ssm_parameter("/app/customersupport/agentcore/lambda_arn")
            
            # 确保Runtime Role有Gateway权限
            console.print("  🔧 配置Runtime Role权限...")
            self.ensure_runtime_gateway_permissions()
            
            # 确保Gateway Role有Policy权限（提前添加）
            console.print("  🔧 配置Gateway Role的Policy权限...")
            self.ensure_gateway_policy_permissions()
            
            console.print("  ✅ Cognito配置已加载")
            console.print(f"  ✅ Machine Client: {self.resources['cognito']['client_id'][:20]}...")
            console.print(f"  ✅ Web Client: {self.resources['cognito']['web_client_id'][:20]}...")
            console.print("  ✅ IAM Roles已加载")
            console.print("  ✅ Lambda ARN已加载")
            
        except Exception as e:
            console.print(f"[red]❌ 加载资源失败: {e}[/red]")
            console.print("[yellow]请确保已运行 ./prereq.sh[/yellow]")
            sys.exit(1)

    def ensure_test_user(self):
        """确保测试用户存在"""
        cognito = boto3.client("cognito-idp", region_name=self.region)
        username = "testuser@example.com"
        password = "MyPassword123!"
        
        try:
            # 检查用户是否存在
            users = cognito.list_users(
                UserPoolId=self.resources["cognito"]["pool_id"],
                Filter=f'email = "{username}"'
            )
            
            if not users.get("Users"):
                console.print(f"  ➕ 创建测试用户: {username}")
                # 创建用户
                cognito.admin_create_user(
                    UserPoolId=self.resources["cognito"]["pool_id"],
                    Username=username,
                    TemporaryPassword="Temp123!",
                    MessageAction="SUPPRESS",
                    UserAttributes=[
                        {"Name": "email", "Value": username}
                    ]
                )
                
                # 设置永久密码
                cognito.admin_set_user_password(
                    UserPoolId=self.resources["cognito"]["pool_id"],
                    Username=username,
                    Password=password,
                    Permanent=True
                )
                console.print(f"  ✅ 测试用户已创建")
            else:
                console.print(f"  ✅ 测试用户已存在")
                
        except Exception as e:
            console.print(f"  ⚠️  创建用户失败: {e}")

    def ensure_runtime_gateway_permissions(self):
        """确保Runtime Role有Gateway和Memory权限"""
        iam = boto3.client("iam")
        role_name = self.resources["runtime_role_arn"].split("/")[-1]
        
        # 1. 添加Gateway权限
        try:
            try:
                iam.get_role_policy(RoleName=role_name, PolicyName="GatewayAccessPolicy")
                console.print("  ✅ Gateway权限已存在")
            except iam.exceptions.NoSuchEntityException:
                console.print("  ➕ 添加Gateway权限...")
                gateway_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "bedrock-agentcore:GetGateway",
                                "bedrock-agentcore:InvokeGateway"
                            ],
                            "Resource": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:gateway/*"
                        }
                    ]
                }
                
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName="GatewayAccessPolicy",
                    PolicyDocument=json.dumps(gateway_policy)
                )
                console.print("  ✅ Gateway权限已添加")
        except Exception as e:
            console.print(f"  ⚠️  添加Gateway权限失败: {e}")
        
        # 2. 添加Memory权限
        try:
            try:
                iam.get_role_policy(RoleName=role_name, PolicyName="MemoryAccessPolicy")
                console.print("  ✅ Memory权限已存在")
            except iam.exceptions.NoSuchEntityException:
                console.print("  ➕ 添加Memory权限...")
                memory_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "bedrock-agentcore:ListEvents",
                                "bedrock-agentcore:CreateEvent",
                                "bedrock-agentcore:GetEvent",
                                "bedrock-agentcore:ListMemories",
                                "bedrock-agentcore:GetMemory",
                                "bedrock-agentcore:ListMemoryRecords",
                                "bedrock-agentcore:GetMemoryRecord",
                                "bedrock-agentcore:RetrieveMemoryRecords"
                            ],
                            "Resource": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:memory/*"
                        }
                    ]
                }
                
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName="MemoryAccessPolicy",
                    PolicyDocument=json.dumps(memory_policy)
                )
                console.print("  ✅ Memory权限已添加")
        except Exception as e:
            console.print(f"  ⚠️  添加Memory权限失败: {e}")
        
        # 3. 添加ECR权限（修复repository名称不匹配问题）
        try:
            try:
                iam.get_role_policy(RoleName=role_name, PolicyName="ECRAccessFix")
                console.print("  ✅ ECR权限已存在")
            except iam.exceptions.NoSuchEntityException:
                console.print("  ➕ 添加ECR权限...")
                ecr_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchGetImage",
                                "ecr:GetDownloadUrlForLayer"
                            ],
                            "Resource": "*"
                        }
                    ]
                }
                
                iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName="ECRAccessFix",
                    PolicyDocument=json.dumps(ecr_policy)
                )
                console.print("  ✅ ECR权限已添加")
        except Exception as e:
            console.print(f"  ⚠️  添加ECR权限失败: {e}")
    
    def ensure_gateway_policy_permissions(self):
        """确保Gateway Role有Policy Engine权限（使用通配符）"""
        iam = boto3.client("iam")
        role_name = self.resources["gateway_role_arn"].split("/")[-1]
        
        console.print("  🔧 配置Gateway Role的Policy权限...")
        
        try:
            # 使用通配符权限确保Policy评估成功
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
            
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName="PolicyEngineAccess",
                PolicyDocument=json.dumps(policy_engine_policy)
            )
            console.print("  ✅ Policy Engine权限已添加（bedrock-agentcore:*）")
        except Exception as e:
            console.print(f"  ⚠️  添加Policy权限失败: {e}")

    def get_cognito_token(self):
        """获取Cognito测试用户的token"""
        cognito = boto3.client("cognito-idp", region_name=self.region)
        
        username = "testuser"
        password = "MyPassword123!"
        client_id = self.resources["cognito"]["client_id"]
        client_secret = self.resources["cognito"]["client_secret"]
        
        # 计算SECRET_HASH
        message = bytes(username + client_id, "utf-8")
        key = bytes(client_secret, "utf-8")
        secret_hash = base64.b64encode(
            hmac.new(key, message, digestmod=hashlib.sha256).digest()
        ).decode()
        
        try:
            auth_response = cognito.initiate_auth(
                ClientId=client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password,
                    "SECRET_HASH": secret_hash,
                },
            )
            return auth_response["AuthenticationResult"]["AccessToken"]
        except Exception as e:
            console.print(f"[yellow]⚠️  无法获取token: {e}[/yellow]")
            return ""

    def deploy(self):
        """主部署流程"""
        console.print(
            Panel.fit(
                "[bold green]🚀 AgentCore E2E 可视化演示 - 自动部署[/bold green]\n"
                f"[cyan]Region: {self.region}[/cyan]\n"
                f"[cyan]Account: {self.account_id}[/cyan]\n\n"
                "[yellow]注意：请确保已运行 ./prereq.sh[/yellow]",
                border_style="green",
            )
        )

        try:
            # 检查前置条件
            self.check_prerequisites()
            
            # 加载现有资源
            self.load_existing_resources()

            # 步骤1: 创建Memory
            console.print("\n[bold cyan]步骤 1/7: 创建AgentCore Memory[/bold cyan]")
            self.create_memory()

            # 步骤2: 创建Gateway
            console.print("\n[bold cyan]步骤 2/7: 创建AgentCore Gateway[/bold cyan]")
            self.create_gateway()

            # 步骤3: 部署CouponTool Lambda
            console.print("\n[bold cyan]步骤 3/7: 部署CouponTool Lambda[/bold cyan]")
            self.deploy_coupon_lambda()

            # 步骤4: 创建Policy Engine
            console.print("\n[bold cyan]步骤 4/7: 创建Policy Engine[/bold cyan]")
            self.deploy_policy_engine()

            # 步骤5: 部署Runtime
            console.print("\n[bold cyan]步骤 5/7: 部署AgentCore Runtime[/bold cyan]")
            try:
                self.deploy_runtime()
            except Exception as e:
                console.print(f"\n[yellow]⚠️  Runtime部署遇到问题，但可能已部分完成[/yellow]")
                # 检查是否有runtime_arn，如果有则继续
                if "runtime_arn" not in self.resources:
                    console.print("[red]❌ 无法继续，Runtime未创建[/red]")
                    raise
                else:
                    console.print("[green]✅ Runtime ARN已保存，继续部署前端[/green]")

            # 步骤6: 部署前端
            console.print("\n[bold cyan]步骤 6/7: 部署前端应用[/bold cyan]")
            self.deploy_frontend()

            # 步骤7: 验证Policy配置
            console.print("\n[bold cyan]步骤 7/7: 验证Policy配置[/bold cyan]")
            self.verify_policy_setup()

            # 显示部署摘要
            self.show_summary()

        except Exception as e:
            console.print(f"\n[bold red]❌ 部署失败: {e}[/bold red]")
            console.print("[yellow]提示: 运行 'python cleanup.py' 清理已创建的资源[/yellow]")
            
            # 显示已创建的资源
            if self.resources:
                console.print("\n[cyan]已创建的资源（保存在deployment_info.yaml）:[/cyan]")
                for key, value in self.resources.items():
                    if key not in ['cognito'] and value:
                        console.print(f"  • {key}: {str(value)[:80]}...")
            
            raise

    def create_memory(self):
        """创建AgentCore Memory"""
        with console.status("[bold green]创建AgentCore Memory（约2-3分钟）..."):
            memory_id = create_agentcore_memory(
                self.config["memory"]["name"],
                self.config["memory"]["description"],
                self.region,
            )
            self.resources["memory_id"] = memory_id
            put_ssm_parameter("/app/customersupport/agentcore/memory_id", memory_id)
            self.save_resources()

        console.print(f"  ✅ Memory ID: {memory_id}")

    def create_gateway(self):
        """创建AgentCore Gateway"""
        with console.status("[bold green]创建AgentCore Gateway..."):
            gateway_id = create_agentcore_gateway(
                self.config["gateway"]["name"],
                self.config["gateway"]["description"],
                self.resources["gateway_role_arn"],
                self.resources["cognito"]["client_id"],
                self.resources["cognito"]["discovery_url"],
                self.resources["lambda_arn"],
                "lambda/api_spec.json",
                self.region,
                web_client_id=self.resources["cognito"]["web_client_id"],  # 传入Web Client
            )
            self.resources["gateway_id"] = gateway_id
            
            # 获取Gateway ARN
            gateway_client = boto3.client("bedrock-agentcore-control", region_name=self.region)
            gateway_info = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
            self.resources["gateway_arn"] = gateway_info["gatewayArn"]
            
            self.save_resources()

        console.print(f"  ✅ Gateway ID: {gateway_id}")
        console.print(f"  ✅ 允许的Clients: Machine + Web")

    def deploy_coupon_lambda(self):
        """部署CouponTool Lambda函数"""
        with console.status("[bold green]创建CouponTool Lambda..."):
            lambda_arn, role_arn = create_coupon_lambda(
                self.config["coupon_lambda"]["name"],
                self.config["coupon_lambda"]["role_name"],
                self.region
            )
            self.resources["coupon_lambda_arn"] = lambda_arn
            self.resources["coupon_lambda_role_arn"] = role_arn
            
            # 先更新Gateway Role权限（添加Coupon Lambda调用权限）
            # 必须在创建Gateway Target之前完成，否则Gateway会校验权限失败
            console.print("  🔧 更新Gateway Role权限...")
            iam_client = boto3.client("iam", region_name=self.region)
            role_name = self.resources["gateway_role_arn"].split("/")[-1]
            
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
                        if lambda_arn not in statement["Resource"]:
                            if isinstance(statement["Resource"], list):
                                statement["Resource"].append(lambda_arn)
                            else:
                                statement["Resource"] = [statement["Resource"], lambda_arn]
                
                # 更新策略
                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName="BedrockAgentPolicy",
                    PolicyDocument=json.dumps(policy_doc)
                )
            except Exception:
                pass
            
            # 等待IAM权限传播
            console.print("  ⏳ 等待IAM权限传播...")
            time.sleep(15)
            
            # 添加Target到Gateway（Gateway会校验Role是否有Lambda调用权限）
            target_id = add_coupon_gateway_target(
                self.resources["gateway_id"],
                self.config["coupon_lambda"]["target_name"],
                lambda_arn,
                self.region
            )
            self.resources["coupon_target_id"] = target_id
            
            self.save_resources()

        console.print(f"  ✅ Lambda ARN: {lambda_arn}")
        console.print(f"  ✅ Target ID: {target_id}")
        console.print("  ✅ Gateway Role权限已更新")

    def deploy_policy_engine(self):
        """部署Policy Engine和规则"""
        with console.status("[bold green]创建Policy Engine..."):
            # 创建Policy Engine
            policy_engine_id = create_policy_engine(
                self.config["policy"]["engine_name"],
                self.region
            )
            self.resources["policy_engine_id"] = policy_engine_id
            
            # 获取Gateway ARN（如果还没有）
            if "gateway_arn" not in self.resources:
                gateway_client = boto3.client("bedrock-agentcore-control", region_name=self.region)
                gateway_info = gateway_client.get_gateway(gatewayIdentifier=self.resources["gateway_id"])
                self.resources["gateway_arn"] = gateway_info["gatewayArn"]
            
            gateway_arn = self.resources["gateway_arn"]
            
            # 删除可能存在的失败Policy
            console.print("  🔧 清理失败的Policy...")
            try:
                gateway_client = boto3.client("bedrock-agentcore-control", region_name=self.region)
                policies = gateway_client.list_policies(policyEngineId=policy_engine_id)
                
                for policy in policies.get('policies', []):
                    if policy['status'] == 'CREATE_FAILED':
                        try:
                            gateway_client.delete_policy(
                                policyEngineId=policy_engine_id,
                                policyId=policy['policyId']
                            )
                            console.print(f"  ✅ 删除失败Policy: {policy['name']}")
                        except Exception:
                            pass
                
                # 等待删除完成
                time.sleep(3)
            except Exception:
                pass
            
            # 创建Policy规则
            policy_ids = create_policy_rules(
                policy_engine_id,
                gateway_arn,
                self.region
            )
            self.resources["policy_ids"] = policy_ids
            
            # 确保Gateway Role有Policy Engine权限
            self.ensure_gateway_policy_permissions()

            # 关联Policy Engine到Gateway
            attach_policy_to_gateway(
                self.resources["gateway_id"],
                policy_engine_id,
                self.config["policy"]["mode"],
                self.region
            )
            
            self.save_resources()

        console.print(f"  ✅ Policy Engine ID: {policy_engine_id}")
        console.print(f"  ✅ 创建了 {len(policy_ids)} 个Policy规则")
        console.print(f"  ✅ Policy模式: {self.config['policy']['mode']}")
        
        # 等待Policy生效
        console.print("  ⏳ 等待Policy规则生效...")
        time.sleep(5)

    def verify_policy_setup(self):
        """验证Policy配置"""
        console.print("  🔍 验证Policy Engine配置...")
        
        gateway_client = boto3.client("bedrock-agentcore-control", region_name=self.region)
        
        # 检查Gateway的Policy配置
        gateway_info = gateway_client.get_gateway(gatewayIdentifier=self.resources["gateway_id"])
        if "policyEngineConfiguration" in gateway_info:
            console.print("  ✅ Policy Engine已关联到Gateway")
            console.print(f"  ✅ 模式: {gateway_info['policyEngineConfiguration']['mode']}")
        else:
            console.print("  ⚠️  Policy Engine未关联到Gateway")
        
        # 检查Policy规则状态
        try:
            response = gateway_client.list_policies(policyEngineId=self.resources["policy_engine_id"])
            active_count = sum(1 for p in response.get("policies", []) if p.get("status") == "ACTIVE")
            failed_count = sum(1 for p in response.get("policies", []) if p.get("status") == "CREATE_FAILED")
            
            console.print(f"  ✅ {active_count} 个Policy规则处于ACTIVE状态")
            
            if failed_count > 0:
                console.print(f"  ⚠️  {failed_count} 个Policy规则失败")
                # 尝试重新创建失败的规则
                console.print("  🔧 尝试重新创建失败的规则...")
                for policy in response.get("policies", []):
                    if policy.get("status") == "CREATE_FAILED":
                        try:
                            gateway_client.delete_policy(
                                policyEngineId=self.resources["policy_engine_id"],
                                policyId=policy["policyId"]
                            )
                        except Exception:
                            pass
                
                time.sleep(3)
                
                # 重新创建Policy规则
                create_policy_rules(
                    self.resources["policy_engine_id"],
                    self.resources["gateway_arn"],
                    self.region
                )
                console.print("  ✅ 失败的规则已重新创建")
                
        except Exception as e:
            console.print(f"  ⚠️  无法检查Policy状态: {e}")
        
        # 检查Gateway Role权限
        console.print("  🔍 验证Gateway Role权限...")
        iam = boto3.client("iam")
        role_name = self.resources["gateway_role_arn"].split("/")[-1]
        
        try:
            policies = iam.list_role_policies(RoleName=role_name)
            if "PolicyEngineAccess" in policies['PolicyNames']:
                console.print("  ✅ Gateway Role有Policy评估权限")
            else:
                console.print("  ⚠️  Gateway Role缺少Policy评估权限")
        except Exception as e:
            console.print(f"  ⚠️  无法检查Role权限: {e}")
        
        # 等待IAM权限传播
        console.print("  ⏳ 等待IAM权限传播（30秒）...")
        time.sleep(30)
        console.print("  ✅ 权限传播完成")

    def deploy_runtime(self):
        """部署AgentCore Runtime"""
        console.print("  [yellow]⏳ 构建并部署Runtime（约5-10分钟）...[/yellow]")

        # 删除旧的配置文件，避免尝试更新不存在的Runtime
        config_files = [".bedrock_agentcore.yaml", "Dockerfile", ".dockerignore"]
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    os.remove(config_file)
                    console.print(f"  🔧 删除旧配置: {config_file}")
                except Exception:
                    pass

        try:
            with console.status("[bold green]部署中..."):
                runtime_arn = deploy_agentcore_runtime(
                    self.config["runtime"]["entrypoint"],
                    self.config["runtime"]["requirements_file"],
                    self.resources["runtime_role_arn"],
                    self.config["runtime"]["agent_name"],
                    self.resources["cognito"]["client_id"],  # Machine Client
                    self.resources["cognito"]["discovery_url"],
                    self.resources["memory_id"],
                    self.region,
                    web_client_id=self.resources["cognito"]["web_client_id"],  # Web Client
                )
                self.resources["runtime_arn"] = runtime_arn
                put_ssm_parameter("/app/customersupport/agentcore/runtime_viz_arn", runtime_arn)
                self.save_resources()

            console.print(f"  ✅ Runtime ARN: {runtime_arn}")
            console.print("  ✅ Runtime已部署（允许Machine + Web Client）")
            
        except Exception as e:
            console.print(f"  [red]❌ Runtime部署失败: {e}[/red]")
            console.print("\n[yellow]可能的原因:[/yellow]")
            console.print("  1. CodeBuild超时（构建时间过长）")
            console.print("  2. Runtime创建失败（检查CloudWatch日志）")
            console.print("  3. 网络问题或资源限制")
            console.print("\n[cyan]建议:[/cyan]")
            console.print("  1. 检查CodeBuild日志")
            console.print("  2. 删除配置文件后重试: rm -f .bedrock_agentcore.yaml Dockerfile .dockerignore")
            console.print("  3. 如果Runtime已创建，手动更新deployment_info.yaml中的runtime_arn")
            
            # 尝试查找已创建的Runtime
            console.print("\n[cyan]查找已创建的Runtime...[/cyan]")
            try:
                control_client = boto3.client('bedrock-agentcore-control', region_name=self.region)
                runtimes = control_client.list_agent_runtimes()
                
                for runtime in runtimes.get('agentRuntimes', []):
                    if 'customer_support_agent' in runtime.get('agentRuntimeId', ''):
                        runtime_id = runtime['agentRuntimeId']
                        runtime_arn = f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/{runtime_id}"
                        console.print(f"  ✅ 找到Runtime: {runtime_arn}")
                        
                        # 保存到resources
                        self.resources["runtime_arn"] = runtime_arn
                        put_ssm_parameter("/app/customersupport/agentcore/runtime_viz_arn", runtime_arn)
                        self.save_resources()
                        
                        console.print("  ✅ Runtime ARN已保存，继续部署...")
                        return  # 继续执行后续步骤
                        
            except Exception as e2:
                console.print(f"  [red]查找Runtime失败: {e2}[/red]")
            
            raise  # 重新抛出异常

    def deploy_frontend(self):
        """部署前端应用"""
        frontend_dir = "frontend"

        if not os.path.exists(frontend_dir):
            console.print("  ⚠️  前端目录不存在，跳过前端部署")
            return

        # 生成.env文件
        console.print("  📝 生成前端配置...")
        env_content = f"""# AgentCore Runtime Configuration
VITE_AGENT_RUNTIME_ARN={self.resources['runtime_arn']}
VITE_AWS_REGION={self.region}

# AgentCore Resource IDs (for Console links)
VITE_POLICY_ENGINE_ID={self.resources.get('policy_engine_id', '')}
VITE_GATEWAY_ID={self.resources.get('gateway_id', '')}
VITE_MEMORY_ID={self.resources.get('memory_id', '')}

# Cognito Configuration (for login)
VITE_COGNITO_USER_POOL_ID={self.resources['cognito']['pool_id']}
VITE_COGNITO_CLIENT_ID={self.resources['cognito']['web_client_id']}
VITE_COGNITO_CLIENT_SECRET=

# Preset Auth Token (optional)
VITE_AUTH_TOKEN={self.resources['cognito']['bearer_token']}
"""
        with open(f"{frontend_dir}/.env", "w") as f:
            f.write(env_content)

        # 构建前端
        console.print("  🔨 构建前端（约1-2分钟）...")
        import subprocess

        try:
            subprocess.run(
                ["npm", "install"],
                cwd=frontend_dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["npm", "run", "build"],
                cwd=frontend_dir,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"  ⚠️  前端构建失败: {e}")
            console.print("  💡 可以稍后手动运行: cd frontend && npm install && npm run build")
            return

        # 部署到S3 + CloudFront
        if self.config["frontend"]["deploy_to_s3"]:
            from utils.aws_helper import (
                fix_cloudfront_oai_policy,
                test_cloudfront_access,
                invalidate_cloudfront_cache,
            )
            
            console.print("  ☁️  创建S3 Bucket...")
            frontend_bucket = f"agentcore-frontend-{self.account_id}"
            bucket_name = create_s3_website_bucket(frontend_bucket, self.region)

            build_dir = f"{frontend_dir}/{self.config['frontend']['build_dir']}"
            console.print("  📤 上传前端文件到S3...")
            upload_directory(build_dir, bucket_name)

            # 检查CloudFront是否已存在
            if "frontend_cloudfront" in self.resources:
                console.print("  🔧 CloudFront已存在，修复OAI策略...")
                distribution_id = self.resources["frontend_cloudfront"]["distribution_id"]
                
                # 修复OAI策略
                if fix_cloudfront_oai_policy(bucket_name, distribution_id, self.region):
                    console.print("  ✅ OAI策略已修复")
                else:
                    console.print("  ⚠️  OAI策略修复失败")
                
                # 失效缓存
                console.print("  🔄 失效CloudFront缓存...")
                if invalidate_cloudfront_cache(distribution_id):
                    console.print("  ✅ 缓存失效请求已提交")
                
                cloudfront_info = self.resources["frontend_cloudfront"]
            else:
                # 创建新的CloudFront
                console.print("  🌐 创建CloudFront分发（约2-3分钟）...")
                with console.status("[bold green]创建CloudFront..."):
                    cloudfront_info = create_cloudfront_distribution(bucket_name, self.region)
                
                # 修复OAI策略（确保正确）
                console.print("  🔧 配置OAI策略...")
                fix_cloudfront_oai_policy(bucket_name, cloudfront_info["distribution_id"], self.region)
                
                # 失效缓存
                invalidate_cloudfront_cache(cloudfront_info["distribution_id"])
            
            self.resources["frontend_bucket"] = bucket_name
            self.resources["frontend_cloudfront"] = cloudfront_info
            self.resources["frontend_url"] = cloudfront_info["url"]
            self.save_resources()

            console.print(f"  ✅ CloudFront URL: {cloudfront_info['url']}")
            
            # 验证访问
            console.print("  🧪 验证CloudFront访问...")
            time.sleep(2)  # 等待2秒
            if test_cloudfront_access(cloudfront_info["url"]):
                console.print("  ✅ CloudFront访问正常")
            else:
                console.print("  [yellow]⏳ CloudFront正在生效中，请等待5-10分钟[/yellow]")
                console.print("  [dim]提示: 可以先使用本地开发模式测试[/dim]")
        else:
            console.print("  ✅ 前端构建完成（本地运行）")
            console.print(f"  💡 运行: cd {frontend_dir} && npm run dev")

    def show_summary(self):
        """显示部署摘要"""
        console.print("\n")
        console.print(
            Panel.fit(
                "[bold green]✅ 部署完成！[/bold green]",
                border_style="green",
            )
        )

        # 资源信息表格
        table = Table(title="📋 部署的资源", show_header=True, header_style="bold cyan")
        table.add_column("资源类型", style="cyan")
        table.add_column("资源ID/ARN", style="green")

        table.add_row("Memory", self.resources.get("memory_id", "N/A"))
        table.add_row("Gateway", self.resources.get("gateway_id", "N/A"))
        table.add_row("Policy Engine", self.resources.get("policy_engine_id", "N/A"))
        table.add_row("Coupon Lambda", self.resources.get("coupon_lambda_arn", "N/A"))
        table.add_row("Runtime", self.resources.get("runtime_arn", "N/A"))
        table.add_row("Lambda", self.resources.get("lambda_arn", "N/A"))

        console.print(table)

        # 访问信息
        console.print("\n[bold cyan]🌐 访问信息：[/bold cyan]")
        if "frontend_url" in self.resources:
            console.print(f"  CloudFront URL: [link]{self.resources['frontend_url']}[/link]")
            console.print("  [yellow]⏳ CloudFront需要5-10分钟生效[/yellow]")
        
        console.print("\n[bold cyan]💻 本地开发（推荐）：[/bold cyan]")
        console.print("  cd frontend && npm run dev")
        console.print("  然后访问: http://localhost:3000")

        # 认证信息
        console.print("\n[bold cyan]🔐 测试账号：[/bold cyan]")
        console.print("  用户名: testuser@example.com")
        console.print("  密码: MyPassword123!")
        console.print(f"  Token: {self.resources['cognito']['bearer_token'][:50] if self.resources['cognito']['bearer_token'] else 'N/A'}...")

        # 注意事项
        console.print("\n[bold yellow]⚠️  注意事项：[/bold yellow]")
        console.print("  • Cognito token有效期2小时")
        console.print("  • Memory首次使用需等待约30秒处理")
        console.print("  • 资源信息已保存到 deployment_info.yaml")
        console.print("  • 推荐使用本地开发模式（npm run dev）")
        console.print(f"  • Policy Engine已启用（模式: {self.config['policy']['mode']}）")
        console.print(f"  • 代金券金额限制: <${self.config['policy']['coupon_limit']}")

        # 下一步
        console.print("\n[bold cyan]📚 下一步：[/bold cyan]")
        console.print("  1. cd frontend && npm run dev")
        console.print("  2. 访问 http://localhost:3000")
        console.print("  3. 使用测试账号登录")
        console.print("  4. 测试Agent功能和工作流可视化")
        console.print("  5. 测试Policy控制: 尝试申请$100和$500代金券")
        console.print("  6. 运行 'python toDelete_test_policy.py' 测试Policy")
        console.print("  7. 运行 'python cleanup.py' 清理资源")


def main():
    """主函数"""
    try:
        deployer = AgentCoreDeployer()
        deployer.deploy()
    except KeyboardInterrupt:
        console.print("\n[yellow]部署已取消[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]错误: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
