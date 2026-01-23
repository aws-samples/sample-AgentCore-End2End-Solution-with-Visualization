"""
本地工具定义 - 从Lab 1复制
"""

import boto3
from strands.tools import tool
from strands_tools import retrieve

# System Prompt
SYSTEM_PROMPT = """You are a helpful and professional customer support assistant for an electronics e-commerce company.
Your role is to:
- Provide accurate information using the tools available to you
- Support the customer with technical information and product specifications
- Be friendly, patient, and understanding with customers
- Always offer additional help after answering questions

You have access to the following tools:
1. get_return_policy() - For warranty and return policy questions
2. get_product_info() - To get information about a specific product
3. get_technical_support() - For troubleshooting issues and technical assistance
4. check_warranty_status() - Check warranty status (via Gateway)
5. web_search() - Search the web for updated information (via Gateway)

Always use the appropriate tool to get accurate, up-to-date information."""


@tool
def get_return_policy(product_category: str) -> str:
    """
    Get return policy information for a specific product category.

    Args:
        product_category: Electronics category (e.g., 'smartphones', 'laptops', 'accessories')

    Returns:
        Formatted return policy details including timeframes and conditions
    """
    return_policies = {
        "smartphones": {
            "window": "30 days",
            "condition": "Original packaging, no physical damage, factory reset required",
            "process": "Online RMA portal or technical support",
            "refund_time": "5-7 business days after inspection",
        },
        "laptops": {
            "window": "30 days",
            "condition": "Original packaging, all accessories, no software modifications",
            "process": "Technical support verification required before return",
            "refund_time": "7-10 business days after inspection",
        },
        "accessories": {
            "window": "30 days",
            "condition": "Unopened packaging preferred, all components included",
            "process": "Online return portal",
            "refund_time": "3-5 business days after receipt",
        },
    }

    policy = return_policies.get(product_category.lower())
    if not policy:
        return f"Return policy for {product_category} not found. Please contact support."

    return (
        f"Return Policy - {product_category.title()}:\\n\\n"
        f"• Return window: {policy['window']} from delivery\\n"
        f"• Condition: {policy['condition']}\\n"
        f"• Process: {policy['process']}\\n"
        f"• Refund timeline: {policy['refund_time']}"
    )


@tool
def get_product_info(product_type: str) -> str:
    """
    Get detailed technical specifications and information for electronics products.

    Args:
        product_type: Electronics product type (e.g., 'laptops', 'smartphones', 'headphones')

    Returns:
        Formatted product information including warranty, features, and policies
    """
    products = {
        "laptops": {
            "warranty": "1-year manufacturer warranty + optional extended coverage",
            "specs": "Intel/AMD processors, 8-32GB RAM, SSD storage, various display sizes",
            "features": "Backlit keyboards, USB-C/Thunderbolt, Wi-Fi 6, Bluetooth 5.0",
        },
        "smartphones": {
            "warranty": "1-year manufacturer warranty",
            "specs": "5G/4G connectivity, 128GB-1TB storage, multiple camera systems",
            "features": "Wireless charging, water resistance, biometric security",
        },
        "headphones": {
            "warranty": "1-year manufacturer warranty",
            "specs": "Wired/wireless options, noise cancellation, 20Hz-20kHz frequency",
            "features": "Active noise cancellation, touch controls, voice assistant",
        },
    }

    product = products.get(product_type.lower())
    if not product:
        return f"Product information for {product_type} not available."

    return (
        f"Technical Information - {product_type.title()}:\\n\\n"
        f"• Warranty: {product['warranty']}\\n"
        f"• Specifications: {product['specs']}\\n"
        f"• Key Features: {product['features']}"
    )


@tool
def get_technical_support(issue_description: str) -> str:
    """
    Get technical support from Knowledge Base.

    Args:
        issue_description: Description of the technical issue

    Returns:
        Technical support information from Knowledge Base
    """
    try:
        # 获取KB ID
        ssm = boto3.client("ssm")
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        region = boto3.Session().region_name

        kb_id = ssm.get_parameter(
            Name=f"/{account_id}-{region}/kb/knowledge-base-id"
        )["Parameter"]["Value"]

        # 使用strands retrieve工具
        tool_use = {
            "toolUseId": "tech_support_query",
            "input": {
                "text": issue_description,
                "knowledgeBaseId": kb_id,
                "region": region,
                "numberOfResults": 3,
                "score": 0.4,
            },
        }

        result = retrieve.retrieve(tool_use)

        if result["status"] == "success":
            return result["content"][0]["text"]
        else:
            return f"Unable to access technical support documentation."

    except Exception as e:
        return f"Technical support temporarily unavailable. Error: {str(e)}"
