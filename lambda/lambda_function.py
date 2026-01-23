"""
Lambda函数 - 提供warranty check和web search工具
"""

import os
import json
import boto3
from check_warranty import check_warranty_status
from web_search import web_search


def get_tool_name(event):
    """从event中提取工具名称"""
    # AgentCore Gateway会在event中传递工具名称
    return event.get("tool_name") or event.get("toolName")


def get_named_parameter(event, name):
    """从event中提取参数"""
    params = event.get("parameters", {})
    return params.get(name)


def lambda_handler(event, context):
    """Lambda处理函数"""
    print(f"Received event: {json.dumps(event)}")

    tool_name = get_tool_name(event)

    if tool_name == "check_warranty_status":
        serial_number = get_named_parameter(event, "serial_number")
        customer_email = get_named_parameter(event, "customer_email")

        if not serial_number:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "serial_number is required"}),
            }

        result = check_warranty_status(serial_number, customer_email)
        return {"statusCode": 200, "body": json.dumps(result)}

    elif tool_name == "web_search":
        keywords = get_named_parameter(event, "keywords")
        region = get_named_parameter(event, "region") or "us-en"
        max_results = get_named_parameter(event, "max_results") or 5

        if not keywords:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "keywords is required"}),
            }

        result = web_search(keywords, region, max_results)
        return {"statusCode": 200, "body": json.dumps(result)}

    else:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unknown tool: {tool_name}"}),
        }
