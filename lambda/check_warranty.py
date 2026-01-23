"""
Warranty检查工具
"""

import os
import boto3
from datetime import datetime


def check_warranty_status(serial_number, customer_email=None):
    """检查保修状态"""
    dynamodb = boto3.resource("dynamodb")
    warranty_table_name = os.environ.get("WARRANTY_TABLE", "CustomerSupport-Warranty")

    try:
        table = dynamodb.Table(warranty_table_name)
        response = table.get_item(Key={"serial_number": serial_number})

        if "Item" not in response:
            return {
                "status": "not_found",
                "message": f"No warranty found for serial number: {serial_number}",
            }

        item = response["Item"]

        # 检查保修是否过期
        warranty_end = datetime.strptime(item["warranty_end_date"], "%Y-%m-%d")
        is_active = warranty_end > datetime.now()

        return {
            "status": "active" if is_active else "expired",
            "serial_number": serial_number,
            "product_name": item.get("product_name"),
            "purchase_date": item.get("purchase_date"),
            "warranty_end_date": item.get("warranty_end_date"),
            "warranty_type": item.get("warranty_type"),
            "customer_id": item.get("customer_id"),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
