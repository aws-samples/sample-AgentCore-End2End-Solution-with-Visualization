"""
Lambda function for CouponTool - 代金券批复工具
"""
import json


def get_named_parameter(event, name):
    """从event中获取参数"""
    if name not in event:
        return None
    return event.get(name)


def approve_coupon(amount: float) -> dict:
    """
    批复代金券
    
    Args:
        amount: 代金券金额
        
    Returns:
        批复结果
    """
    if amount <= 0:
        return {
            "success": False,
            "message": f"❌ 金额必须大于0，当前金额: ${amount}"
        }
    
    # 模拟批复成功
    return {
        "success": True,
        "message": f"✅ 代金券批复成功！金额: ${amount}",
        "coupon_code": f"COUPON-{int(amount * 100)}",
        "amount": amount
    }


def lambda_handler(event, context):
    """Lambda处理函数"""
    print(f"Event: {event}")
    print(f"Context: {context}")
    
    try:
        # 从context中获取工具名称
        extended_tool_name = context.client_context.custom["bedrockAgentCoreToolName"]
        resource = extended_tool_name.split("___")[1]
        
        print(f"Tool name: {resource}")
        
        if resource == "CouponTool":
            # 获取金额参数
            amount = get_named_parameter(event=event, name="amount")
            
            if amount is None:
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "success": False,
                        "message": "❌ 请提供amount参数"
                    })
                }
            
            # 转换为浮点数
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                return {
                    "statusCode": 400,
                    "body": json.dumps({
                        "success": False,
                        "message": f"❌ 金额格式错误: {amount}"
                    })
                }
            
            # 批复代金券
            result = approve_coupon(amount)
            
            return {
                "statusCode": 200,
                "body": json.dumps(result)
            }
        
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "success": False,
                    "message": f"❌ 未知的工具名称: {resource}"
                })
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "message": f"❌ 处理错误: {str(e)}"
            })
        }
