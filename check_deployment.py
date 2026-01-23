#!/usr/bin/env python3
"""
检查部署状态脚本
"""

import yaml
import boto3
from rich.console import Console
from rich.table import Table

console = Console()


def check_deployment():
    """检查部署状态"""
    try:
        with open("deployment_info.yaml", "r") as f:
            resources = yaml.safe_load(f)
    except FileNotFoundError:
        console.print("[red]未找到 deployment_info.yaml[/red]")
        console.print("[yellow]请先运行 python deploy.py[/yellow]")
        return

    console.print("\n[bold cyan]📊 部署状态检查[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("资源", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("ID/ARN")

    # 检查各个资源
    checks = [
        ("Memory", resources.get("memory_id")),
        ("Gateway", resources.get("gateway_id")),
        ("Runtime", resources.get("runtime_arn")),
        ("Lambda", resources.get("lambda_arn")),
        ("Frontend", resources.get("frontend_url")),
    ]

    for name, value in checks:
        status = "✅ 已部署" if value else "❌ 未部署"
        table.add_row(name, status, str(value)[:60] if value else "N/A")

    console.print(table)

    # 显示访问信息
    if resources.get("frontend_url"):
        console.print(f"\n[bold green]🌐 前端URL:[/bold green] {resources['frontend_url']}")

    console.print(f"\n[bold cyan]🔐 测试账号:[/bold cyan]")
    console.print(f"  Token: {resources['cognito']['bearer_token'][:50]}...")


if __name__ == "__main__":
    check_deployment()
