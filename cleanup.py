#!/usr/bin/env python3
"""
AgentCore E2E 可视化演示 - 资源清理脚本

这个脚本只清理AgentCore资源（Memory、Gateway、Runtime、前端）
基础资源（DynamoDB、Lambda、Cognito等）需要通过CloudFormation删除
"""

import os
import sys
import yaml
import boto3
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel

# 添加utils到路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.agentcore_helper import (
    delete_agentcore_memory,
    delete_agentcore_gateway,
    delete_agentcore_runtime,
    delete_policy_engine,
    delete_coupon_lambda,
)
from utils.aws_helper import delete_s3_bucket

console = Console()


class AgentCoreCleanup:
    """AgentCore资源清理器"""

    def __init__(self, deployment_file="deployment_info.yaml"):
        """初始化清理器"""
        self.deployment_file = deployment_file
        self.resources = self.load_resources()

    def load_resources(self):
        """加载资源信息"""
        if not os.path.exists(self.deployment_file):
            console.print(f"[red]错误: 找不到 {self.deployment_file}[/red]")
            console.print("[yellow]提示: 请确保在部署目录中运行此脚本[/yellow]")
            sys.exit(1)

        with open(self.deployment_file, "r") as f:
            return yaml.safe_load(f)

    def cleanup(self):
        """清理AgentCore资源"""
        console.print(
            Panel.fit(
                "[bold red]🗑️  AgentCore 资源清理[/bold red]\n"
                "[yellow]这将删除Memory、Gateway、Runtime和前端[/yellow]\n"
                "[cyan]基础资源需要通过CloudFormation删除[/cyan]",
                border_style="red",
            )
        )

        # 显示将要删除的资源
        console.print("\n[bold cyan]将要删除的资源：[/bold cyan]")
        console.print(f"  • Runtime: {self.resources.get('runtime_arn', 'N/A')}")
        console.print(f"  • Gateway: {self.resources.get('gateway_id', 'N/A')}")
        console.print(f"  • Policy Engine: {self.resources.get('policy_engine_id', 'N/A')}")
        console.print(f"  • Coupon Lambda: {self.resources.get('coupon_lambda_arn', 'N/A')}")
        console.print(f"  • Memory: {self.resources.get('memory_id', 'N/A')}")
        console.print(f"  • 前端S3: {self.resources.get('frontend_url', 'N/A')}")

        console.print("\n[bold yellow]不会删除的资源（需手动删除CloudFormation）：[/bold yellow]")
        console.print("  • DynamoDB表")
        console.print("  • Lambda函数")
        console.print("  • Knowledge Base")
        console.print("  • Cognito User Pool")
        console.print("  • IAM Roles")

        if not Confirm.ask("\n[bold red]确认删除AgentCore资源？[/bold red]"):
            console.print("[yellow]取消清理[/yellow]")
            return

        console.print("\n[bold green]开始清理资源...[/bold green]\n")

        try:
            # 删除前端
            self.delete_frontend()
            
            # 删除Runtime
            self.delete_runtime()
            
            # 删除Gateway (会自动删除Policy Engine关联)
            self.delete_gateway()
            
            # 删除Policy Engine
            self.delete_policy_engine()
            
            # 删除Coupon Lambda
            self.delete_coupon_lambda()
            
            # 删除Memory
            self.delete_memory()

            # 删除部署信息文件
            if os.path.exists(self.deployment_file):
                os.remove(self.deployment_file)
                console.print(f"  ✅ 已删除 {self.deployment_file}")

            console.print("\n[bold green]✅ AgentCore资源清理完成！[/bold green]")
            console.print("\n[bold cyan]清理基础资源（可选）：[/bold cyan]")
            console.print("  aws cloudformation delete-stack --stack-name CustomerSupportStackInfra")
            console.print("  aws cloudformation delete-stack --stack-name CustomerSupportStackCognito")

        except Exception as e:
            console.print(f"\n[bold red]❌ 清理过程中出错: {e}[/bold red]")
            raise

    def delete_frontend(self):
        """删除前端资源"""
        console.print("[cyan]步骤 1/4: 删除前端资源[/cyan]")
        
        # 删除CloudFront分发
        if "frontend_cloudfront" in self.resources:
            from utils.aws_helper import delete_cloudfront_distribution
            
            distribution_id = self.resources["frontend_cloudfront"]["distribution_id"]
            console.print(f"  🌐 删除CloudFront分发（约5-10分钟）...")
            with console.status("[bold green]删除CloudFront..."):
                delete_cloudfront_distribution(distribution_id)
            console.print(f"  ✅ 已删除CloudFront分发")
        
        # 删除S3 bucket
        if "frontend_bucket" in self.resources:
            delete_s3_bucket(self.resources["frontend_bucket"])
            console.print(f"  ✅ 已删除前端bucket: {self.resources['frontend_bucket']}")
        elif "frontend_url" in self.resources:
            # 向后兼容旧版本
            frontend_bucket = self.resources["frontend_url"].split("//")[1].split(".")[0]
            delete_s3_bucket(frontend_bucket)
            console.print(f"  ✅ 已删除前端bucket: {frontend_bucket}")
        else:
            console.print("  ⏭️  跳过（未部署到S3）")

    def delete_runtime(self):
        """删除Runtime"""
        console.print("\n[cyan]步骤 2/4: 删除AgentCore Runtime[/cyan]")
        if "runtime_arn" in self.resources:
            with console.status("[bold green]删除Runtime..."):
                delete_agentcore_runtime(self.resources["runtime_arn"])
            console.print(f"  ✅ 已删除Runtime")
        else:
            console.print("  ⏭️  跳过（未创建）")

    def delete_gateway(self):
        """删除Gateway"""
        console.print("\n[cyan]步骤 3/4: 删除AgentCore Gateway[/cyan]")
        if "gateway_id" in self.resources:
            with console.status("[bold green]删除Gateway..."):
                delete_agentcore_gateway(self.resources["gateway_id"])
            console.print(f"  ✅ 已删除Gateway")
        else:
            console.print("  ⏭️  跳过（未创建）")

    def delete_memory(self):
        """删除Memory"""
        console.print("\n[cyan]步骤 6/6: 删除AgentCore Memory[/cyan]")
        if "memory_id" in self.resources:
            with console.status("[bold green]删除Memory..."):
                delete_agentcore_memory(self.resources["memory_id"])
            console.print(f"  ✅ 已删除Memory")
        else:
            console.print("  ⏭️  跳过（未创建）")

    def delete_policy_engine(self):
        """删除Policy Engine"""
        console.print("\n[cyan]步骤 4/6: 删除Policy Engine[/cyan]")
        if "policy_engine_id" in self.resources:
            with console.status("[bold green]删除Policy Engine..."):
                region = boto3.Session().region_name
                delete_policy_engine(self.resources["policy_engine_id"], region)
            console.print(f"  ✅ 已删除Policy Engine")
        else:
            console.print("  ⏭️  跳过（未创建）")

    def delete_coupon_lambda(self):
        """删除Coupon Lambda"""
        console.print("\n[cyan]步骤 5/6: 删除Coupon Lambda[/cyan]")
        if "coupon_lambda_arn" in self.resources:
            with console.status("[bold green]删除Coupon Lambda..."):
                region = boto3.Session().region_name
                # 从deployment_info.yaml读取配置
                import yaml
                with open("config.yaml", "r") as f:
                    config = yaml.safe_load(f)
                
                delete_coupon_lambda(
                    config["coupon_lambda"]["name"],
                    config["coupon_lambda"]["role_name"],
                    region
                )
            console.print(f"  ✅ 已删除Coupon Lambda")
        else:
            console.print("  ⏭️  跳过（未创建）")


def main():
    """主函数"""
    try:
        cleanup = AgentCoreCleanup()
        cleanup.cleanup()
    except KeyboardInterrupt:
        console.print("\n[yellow]清理已取消[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]错误: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
