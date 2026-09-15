#!/usr/bin/env python3
"""
Brave Search Helper — FREE (2,000 queries/month, no card needed)
Replaces Firecrawl/web_search (which has billing issues).

Usage:
    python3 brave-search.py "Federal Reserve rate decision July 2026"
    python3 brave-search.py "BTC price action" --count 5
"""

import json
import sys
import argparse
import subprocess
import urllib.parse

BRAVE_KEY = "BSA2e1OOGDifa2e3_hQpOAF-D7qvqux"
BASE_URL = "https://api.search.brave.com/res/v1/web/search"


def brave_search(query, count=5):
    """Search via Brave API (FREE tier)."""
    encoded_q = urllib.parse.quote(query, safe="")
    url = f"{BASE_URL}?q={encoded_q}&count={count}"
    cmd = [
        "curl", "-s", "--max-time", "20", "--compressed", url,
        "-H", "Accept: application/json",
        "-H", "Accept-Encoding: gzip",
        "-H", f"X-Subscription-Token: {BRAVE_KEY}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        data = json.loads(result.stdout)
    except Exception as e:
        print(f"❌ Search error: {e}")
        return []

    results = []
    for r in data.get("web", {}).get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("description", ""),
        })
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Brave Search (FREE)")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--count", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    results = brave_search(args.query, args.count)
    print(f"\n🔍 Brave Search: '{args.query}' ({len(results)} results)\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['title'][:80]}")
        print(f"     {r['url']}")
        print(f"     {r['description'][:150]}")
        print()
