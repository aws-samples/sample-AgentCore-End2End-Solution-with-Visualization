"""
AWS资源创建和管理辅助函数
"""

import os
import json
import time
import zipfile
import tempfile
import base64
import hashlib
import hmac
from decimal import Decimal
from pathlib import Path
import boto3
from botocore.exceptions import ClientError


def create_dynamodb_table(table_name, attributes, key_schema, gsi=None):
    """创建DynamoDB表"""
    dynamodb = boto3.client("dynamodb")

    try:
        params = {
            "TableName": table_name,
            "AttributeDefinitions": attributes,
            "KeySchema": key_schema,
            "BillingMode": "PAY_PER_REQUEST",
        }

        if gsi:
            params["GlobalSecondaryIndexes"] = gsi

        response = dynamodb.create_table(**params)

        # 等待表创建完成
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=table_name)

        return response["TableDescription"]["TableArn"]

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            # 表已存在
            response = dynamodb.describe_table(TableName=table_name)
            return response["Table"]["TableArn"]
        raise


def populate_test_data(warranty_table, customer_table):
    """填充测试数据"""
    dynamodb = boto3.resource("dynamodb")

    # 客户数据
    customer_data = [
        {
            "customer_id": "CUST001",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@email.com",
            "phone": "+1-555-0101",
        },
        {
            "customer_id": "CUST002",
            "first_name": "Sarah",
            "last_name": "Johnson",
            "email": "sarah.johnson@email.com",
            "phone": "+1-555-0102",
        },
        {
            "customer_id": "CUST003",
            "first_name": "Mike",
            "last_name": "Davis",
            "email": "mike.davis@email.com",
            "phone": "+1-555-0103",
        },
    ]

    # 保修数据
    warranty_data = [
        {
            "serial_number": "ABC12345678",
            "customer_id": "CUST001",
            "product_name": "SmartPhone Pro Max 128GB",
            "purchase_date": "2023-01-15",
            "warranty_end_date": "2025-01-15",
            "warranty_type": "Extended Warranty",
        },
        {
            "serial_number": "MNO33333333",
            "customer_id": "CUST002",
            "product_name": "Gaming Console Pro",
            "purchase_date": "2023-11-25",
            "warranty_end_date": "2024-11-25",
            "warranty_type": "Gaming Warranty",
        },
    ]

    # 插入客户数据
    customer_tbl = dynamodb.Table(customer_table)
    with customer_tbl.batch_writer() as batch:
        for item in customer_data:
            batch.put_item(Item=item)

    # 插入保修数据
    warranty_tbl = dynamodb.Table(warranty_table)
    with warranty_tbl.batch_writer() as batch:
        for item in warranty_data:
            batch.put_item(Item=item)


def create_s3_bucket(bucket_name, region):
    """创建S3 Bucket"""
    s3 = boto3.client("s3", region_name=region)

    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        return bucket_name
    except ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            return bucket_name
        raise


def upload_directory(local_dir, bucket_name, s3_prefix=""):
    """上传目录到S3（设置正确的Content-Type）"""
    import mimetypes
    
    s3 = boto3.client("s3")
    local_path = Path(local_dir)

    if not local_path.exists():
        return

    for file_path in local_path.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_path)
            s3_key = str(Path(s3_prefix) / relative_path)
            
            # 猜测Content-Type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"
            
            # 上传时设置Content-Type
            extra_args = {"ContentType": content_type}
            s3.upload_file(str(file_path), bucket_name, s3_key, ExtraArgs=extra_args)


def create_s3_website_bucket(bucket_name, region):
    """创建S3 bucket（用于CloudFront）"""
    s3 = boto3.client("s3", region_name=region)

    # 创建bucket（不配置为静态网站，使用CloudFront）
    create_s3_bucket(bucket_name, region)

    return bucket_name


def fix_cloudfront_oai_policy(bucket_name, distribution_id, region):
    """修复CloudFront OAI策略（确保S3 bucket策略与CloudFront使用的OAI匹配）"""
    cloudfront = boto3.client("cloudfront")
    s3 = boto3.client("s3", region_name=region)
    
    try:
        # 1. 获取CloudFront使用的OAI
        dist_config = cloudfront.get_distribution_config(Id=distribution_id)
        oai_path = dist_config['DistributionConfig']['Origins']['Items'][0]['S3OriginConfig']['OriginAccessIdentity']
        oai_id = oai_path.split('/')[-1]
        
        # 2. 获取OAI的Canonical User ID
        oai_detail = cloudfront.get_cloud_front_origin_access_identity(Id=oai_id)
        canonical_user = oai_detail['CloudFrontOriginAccessIdentity']['S3CanonicalUserId']
        
        # 3. 更新S3 bucket策略
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "CloudFrontOAIAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "CanonicalUser": canonical_user
                    },
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                }
            ],
        }
        
        s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(bucket_policy))
        
        return True
    except Exception as e:
        print(f"Failed to fix OAI policy: {e}")
        return False


def test_cloudfront_access(cloudfront_url):
    """测试CloudFront是否可以访问"""
    import requests
    
    try:
        response = requests.get(f"{cloudfront_url}/index.html", timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def invalidate_cloudfront_cache(distribution_id):
    """失效CloudFront缓存"""
    cloudfront = boto3.client("cloudfront")
    
    try:
        cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": str(int(time.time() * 1000)),
            }
        )
        return True
    except Exception as e:
        print(f"Failed to invalidate cache: {e}")
        return False


def create_cloudfront_distribution(bucket_name, region):
    """创建CloudFront分发"""
    cloudfront = boto3.client("cloudfront")
    
    # 创建Origin Access Identity
    try:
        oai_response = cloudfront.create_cloud_front_origin_access_identity(
            CloudFrontOriginAccessIdentityConfig={
                "CallerReference": f"{bucket_name}-{int(time.time())}",
                "Comment": f"OAI for {bucket_name}",
            }
        )
        oai_id = oai_response["CloudFrontOriginAccessIdentity"]["Id"]
        oai_canonical_user = oai_response["CloudFrontOriginAccessIdentity"]["S3CanonicalUserId"]
    except ClientError as e:
        if "already exists" in str(e).lower():
            # 获取现有OAI
            oais = cloudfront.list_cloud_front_origin_access_identities()
            for oai in oais.get("CloudFrontOriginAccessIdentityList", {}).get("Items", []):
                if bucket_name in oai.get("Comment", ""):
                    oai_id = oai["Id"]
                    # 获取完整的OAI信息以获取Canonical User ID
                    oai_detail = cloudfront.get_cloud_front_origin_access_identity(Id=oai_id)
                    oai_canonical_user = oai_detail["CloudFrontOriginAccessIdentity"]["S3CanonicalUserId"]
                    break
        else:
            raise

    # 更新S3 bucket策略，允许OAI访问
    s3 = boto3.client("s3", region_name=region)
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CloudFrontOAIAccess",
                "Effect": "Allow",
                "Principal": {
                    "CanonicalUser": oai_canonical_user
                },
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            }
        ],
    }
    
    s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(bucket_policy))

    # 创建CloudFront分发
    try:
        distribution_config = {
            "CallerReference": f"{bucket_name}-{int(time.time())}",
            "Comment": f"Distribution for {bucket_name}",
            "Enabled": True,
            "DefaultRootObject": "index.html",
            "Origins": {
                "Quantity": 1,
                "Items": [
                    {
                        "Id": f"{bucket_name}-origin",
                        "DomainName": f"{bucket_name}.s3.{region}.amazonaws.com",
                        "S3OriginConfig": {
                            "OriginAccessIdentity": f"origin-access-identity/cloudfront/{oai_id}"
                        },
                    }
                ],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": f"{bucket_name}-origin",
                "ViewerProtocolPolicy": "redirect-to-https",
                "AllowedMethods": {
                    "Quantity": 2,
                    "Items": ["GET", "HEAD"],
                    "CachedMethods": {
                        "Quantity": 2,
                        "Items": ["GET", "HEAD"],
                    },
                },
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {"Forward": "none"},
                },
                "MinTTL": 0,
                "DefaultTTL": 86400,
                "MaxTTL": 31536000,
                "Compress": True,
                "TrustedSigners": {
                    "Enabled": False,
                    "Quantity": 0,
                },
            },
            "CustomErrorResponses": {
                "Quantity": 1,
                "Items": [
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/index.html",
                        "ResponseCode": "200",
                        "ErrorCachingMinTTL": 300,
                    }
                ],
            },
        }

        distribution_response = cloudfront.create_distribution(
            DistributionConfig=distribution_config
        )
        
        distribution_id = distribution_response["Distribution"]["Id"]
        domain_name = distribution_response["Distribution"]["DomainName"]
        
        return {
            "distribution_id": distribution_id,
            "domain_name": domain_name,
            "url": f"https://{domain_name}",
            "oai_id": oai_id,
        }
        
    except ClientError as e:
        if "already exists" in str(e).lower():
            # 获取现有分发
            distributions = cloudfront.list_distributions()
            for dist in distributions.get("DistributionList", {}).get("Items", []):
                if bucket_name in dist.get("Comment", ""):
                    return {
                        "distribution_id": dist["Id"],
                        "domain_name": dist["DomainName"],
                        "url": f"https://{dist['DomainName']}",
                        "oai_id": oai_id,
                    }
        raise


def delete_cloudfront_distribution(distribution_id):
    """删除CloudFront分发"""
    cloudfront = boto3.client("cloudfront")
    
    try:
        # 获取当前配置
        response = cloudfront.get_distribution_config(Id=distribution_id)
        config = response["DistributionConfig"]
        etag = response["ETag"]
        
        # 禁用分发
        if config["Enabled"]:
            config["Enabled"] = False
            cloudfront.update_distribution(
                Id=distribution_id,
                DistributionConfig=config,
                IfMatch=etag,
            )
            
            # 等待分发禁用
            waiter = cloudfront.get_waiter("distribution_deployed")
            waiter.wait(Id=distribution_id)
            
            # 重新获取ETag
            response = cloudfront.get_distribution_config(Id=distribution_id)
            etag = response["ETag"]
        
        # 删除分发
        cloudfront.delete_distribution(Id=distribution_id, IfMatch=etag)
        
    except ClientError:
        pass


def create_cognito_pool(pool_name, client_name, username, password, region):
    """创建Cognito User Pool"""
    cognito = boto3.client("cognito-idp", region_name=region)

    # 创建User Pool
    pool_response = cognito.create_user_pool(
        PoolName=pool_name,
        Policies={"PasswordPolicy": {"MinimumLength": 8}},
    )
    pool_id = pool_response["UserPool"]["Id"]

    # 创建App Client
    client_response = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=True,
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
        ],
    )
    client_id = client_response["UserPoolClient"]["ClientId"]
    client_secret = client_response["UserPoolClient"]["ClientSecret"]

    # 创建测试用户
    cognito.admin_create_user(
        UserPoolId=pool_id,
        Username=username,
        TemporaryPassword="Temp123!",
        MessageAction="SUPPRESS",
    )

    # 设置永久密码
    cognito.admin_set_user_password(
        UserPoolId=pool_id,
        Username=username,
        Password=password,
        Permanent=True,
    )

    # 获取access token
    message = bytes(username + client_id, "utf-8")
    key = bytes(client_secret, "utf-8")
    secret_hash = base64.b64encode(
        hmac.new(key, message, digestmod=hashlib.sha256).digest()
    ).decode()

    auth_response = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": password,
            "SECRET_HASH": secret_hash,
        },
    )

    bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"

    return {
        "pool_id": pool_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "secret_hash": secret_hash,
        "bearer_token": bearer_token,
        "discovery_url": discovery_url,
    }


def create_lambda_function(
    function_name, role_arn, code_dir, handler, runtime, timeout, memory_size, env_vars
):
    """创建Lambda函数"""
    lambda_client = boto3.client("lambda")

    # 打包Lambda代码
    zip_path = package_lambda_code(code_dir)

    try:
        with open(zip_path, "rb") as f:
            zip_content = f.read()

        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime=runtime,
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": zip_content},
            Timeout=timeout,
            MemorySize=memory_size,
            Environment={"Variables": env_vars},
        )

        return response["FunctionArn"]

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            # 函数已存在，更新代码
            lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=zip_content,
            )
            response = lambda_client.get_function(FunctionName=function_name)
            return response["Configuration"]["FunctionArn"]
        raise
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)


def package_lambda_code(code_dir):
    """打包Lambda代码"""
    zip_path = tempfile.mktemp(suffix=".zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        code_path = Path(code_dir)
        for file_path in code_path.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith(".pyc"):
                arcname = file_path.relative_to(code_path)
                zipf.write(file_path, arcname)

    return zip_path


def create_iam_roles(region, account_id):
    """创建所有需要的IAM角色"""
    iam = boto3.client("iam")
    roles = {}

    # Lambda Role
    lambda_role_name = "AgentCoreLambdaRole"
    lambda_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    lambda_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": "arn:aws:logs:*:*:*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                "Resource": f"arn:aws:dynamodb:{region}:{account_id}:table/*",
            },
        ],
    }

    roles["lambda_role_arn"] = create_or_update_role(
        iam, lambda_role_name, lambda_trust_policy, lambda_policy
    )

    # Gateway Role
    gateway_role_name = "AgentCoreGatewayRole"
    gateway_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    gateway_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": f"arn:aws:lambda:{region}:{account_id}:function:*",
            }
        ],
    }

    roles["gateway_role_arn"] = create_or_update_role(
        iam, gateway_role_name, gateway_trust_policy, gateway_policy
    )

    # Runtime Role
    runtime_role_name = "AgentCoreRuntimeRole"
    runtime_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    },
                },
            }
        ],
    }

    runtime_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": "arn:aws:bedrock:*::foundation-model/*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*",
                ],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": "arn:aws:logs:*:*:*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                "Resource": "*",
            },
        ],
    }

    roles["runtime_role_arn"] = create_or_update_role(
        iam, runtime_role_name, runtime_trust_policy, runtime_policy
    )

    return roles


def create_or_update_role(iam, role_name, trust_policy, policy_document):
    """创建或更新IAM角色"""
    try:
        # 尝试创建角色
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
        )
        role_arn = response["Role"]["Arn"]

        # 附加策略
        policy_name = f"{role_name}Policy"
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

        # 等待角色生效
        time.sleep(10)

        return role_arn

    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            # 角色已存在，获取ARN
            response = iam.get_role(RoleName=role_name)
            return response["Role"]["Arn"]
        raise


def create_knowledge_base(kb_name, description, bucket_name, embedding_model, region, account_id):
    """创建Knowledge Base"""
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    # 创建Knowledge Base
    try:
        kb_response = bedrock_agent.create_knowledge_base(
            name=kb_name,
            description=description,
            roleArn=f"arn:aws:iam::{account_id}:role/service-role/AmazonBedrockExecutionRoleForKnowledgeBase",
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": f"arn:aws:bedrock:{region}::foundation-model/{embedding_model}"
                },
            },
            storageConfiguration={
                "type": "OPENSEARCH_SERVERLESS",
                "opensearchServerlessConfiguration": {
                    "collectionArn": f"arn:aws:aoss:{region}:{account_id}:collection/kb-collection",
                    "vectorIndexName": "bedrock-knowledge-base-index",
                    "fieldMapping": {
                        "vectorField": "vector",
                        "textField": "text",
                        "metadataField": "metadata",
                    },
                },
            },
        )

        kb_id = kb_response["knowledgeBase"]["knowledgeBaseId"]

        # 创建Data Source
        ds_response = bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name=f"{kb_name}-DataSource",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{bucket_name}",
                },
            },
        )

        ds_id = ds_response["dataSource"]["dataSourceId"]

        # 开始同步
        bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
        )

        return {"kb_id": kb_id, "ds_id": ds_id}

    except ClientError as e:
        # 简化处理：如果失败就返回空
        return {"kb_id": None, "ds_id": None}


# 删除函数
def delete_dynamodb_table(table_name):
    """删除DynamoDB表"""
    dynamodb = boto3.client("dynamodb")
    try:
        dynamodb.delete_table(TableName=table_name)
    except ClientError:
        pass


def delete_s3_bucket(bucket_name):
    """删除S3 Bucket（包括所有对象）"""
    s3 = boto3.resource("s3")
    try:
        bucket = s3.Bucket(bucket_name)
        bucket.objects.all().delete()
        bucket.delete()
    except ClientError:
        pass


def delete_cognito_pool(pool_id):
    """删除Cognito User Pool"""
    cognito = boto3.client("cognito-idp")
    try:
        cognito.delete_user_pool(UserPoolId=pool_id)
    except ClientError:
        pass


def delete_lambda_function(function_name):
    """删除Lambda函数"""
    lambda_client = boto3.client("lambda")
    try:
        lambda_client.delete_function(FunctionName=function_name)
    except ClientError:
        pass


def delete_iam_roles():
    """删除所有IAM角色"""
    iam = boto3.client("iam")
    role_names = ["AgentCoreLambdaRole", "AgentCoreGatewayRole", "AgentCoreRuntimeRole"]

    for role_name in role_names:
        try:
            # 删除内联策略
            policies = iam.list_role_policies(RoleName=role_name)
            for policy_name in policies["PolicyNames"]:
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

            # 删除角色
            iam.delete_role(RoleName=role_name)
        except ClientError:
            pass


def delete_knowledge_base(kb_id):
    """删除Knowledge Base"""
    bedrock_agent = boto3.client("bedrock-agent")
    try:
        bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
    except ClientError:
        pass
