"""
Web搜索工具 - 使用DuckDuckGo
"""

try:
    from duckduckgo_search import DDGS
except ImportError:
    # 如果没有安装，返回模拟结果
    DDGS = None


def web_search(keywords, region="us-en", max_results=5):
    """搜索网络"""
    if DDGS is None:
        return {
            "status": "error",
            "message": "Web search not available (duckduckgo_search not installed)",
        }

    try:
        results = DDGS().text(keywords, region=region, max_results=max_results)
        return {"status": "success", "results": results if results else []}
    except Exception as e:
        return {"status": "error", "message": str(e)}
