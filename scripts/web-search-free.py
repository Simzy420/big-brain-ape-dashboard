"""
Free Web Search Tool — Powered by DuckDuckGo (ddgs package)
No API key required. No credits. Unlimited searches.

This replaces paid search backends (Firecrawl, Brave, Exa) for the trading agent.

Usage:
    from web_search_free import web_search, search_macro_news, search_asset_news
    
    # General search
    results = web_search("Iran oil crisis August 2026")
    
    # Pre-built macro search
    news = search_macro_news()
    
    # Asset-specific news
    oil_news = search_asset_news("Brent oil")
    gold_news = search_asset_news("Gold price")
"""

from ddgs import DDGS


def web_search(query: str, max_results: int = 8) -> list:
    """
    Free web search using DuckDuckGo.
    Returns a list of results with title, link, and snippet.
    """
    results = []
    
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title"),
                "link": r.get("href") or r.get("url"),
                "snippet": r.get("body") or r.get("description")
            })
    
    return results


def search_macro_news() -> dict:
    """
    Search for the latest macro trading news across all key categories.
    Returns a dictionary with categorized results.
    
    Covers: Fed policy, global liquidity, DXY/dollar, oil/geopolitics, 
    crypto sentiment, gold, and key economic events.
    """
    categories = {
        "fed_policy": "Federal Reserve interest rate decision August 2026",
        "global_liquidity": "global liquidity M2 money supply central bank August 2026",
        "dollar_dxy": "DXY dollar index movement August 2026",
        "oil_geopolitics": "Iran Hormuz oil crisis latest August 2026",
        "crypto_sentiment": "Bitcoin crypto market sentiment August 2026",
        "gold": "gold price record high August 2026",
        "economy": "US economy GDP inflation jobs August 2026",
    }
    
    all_results = {}
    for category, query in categories.items():
        try:
            all_results[category] = web_search(query, max_results=3)
        except Exception as e:
            all_results[category] = [{"error": str(e)}]
    
    return all_results


def search_asset_news(asset: str, max_results: int = 5) -> list:
    """
    Search for latest news about a specific asset.
    
    Examples:
        search_asset_news("Brent oil")
        search_asset_news("Gold")
        search_asset_news("Bitcoin")
        search_asset_news("NVDA stock")
        search_asset_news("S&P 500")
    """
    query = f"{asset} latest news price analysis August 2026"
    return web_search(query, max_results=max_results)


def search_geopolitical() -> list:
    """Search for latest geopolitical developments affecting markets."""
    queries = [
        "Iran US conflict latest update August 2026",
        "Middle East war oil supply disruption August 2026",
        "Strait of Hormuz shipping disruption August 2026",
        "Trump tariffs trade war latest August 2026",
    ]
    
    all_results = []
    for q in queries:
        try:
            results = web_search(q, max_results=2)
            all_results.extend(results)
        except:
            pass
    
    return all_results


def format_search_results(results: list) -> str:
    """Format search results for display."""
    if not results:
        return "No results found."
    
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   {r.get('link', '')}")
        lines.append(f"   {r.get('snippet', '')[:200]}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("DUCKDUCKGO FREE WEB SEARCH — TEST")
    print("=" * 60)
    
    # Test 1: Basic search
    print("\n--- Test 1: Iran Oil Crisis ---")
    results = web_search("Iran Hormuz oil crisis August 2026", max_results=3)
    print(format_search_results(results))
    
    # Test 2: Macro news
    print("\n--- Test 2: Macro News Categories ---")
    macro = search_macro_news()
    for category, results in macro.items():
        print(f"\n  [{category.upper()}]")
        if results and isinstance(results, list) and len(results) > 0:
            for r in results[:2]:
                title = r.get("title", "No title")
                snippet = r.get("snippet", "")[:100]
                print(f"    - {title}")
                print(f"      {snippet}")
        elif isinstance(results, list) and len(results) == 0:
            print("    (no results)")
        else:
            print(f"    Error: {results}")
