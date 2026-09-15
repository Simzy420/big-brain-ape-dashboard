#!/usr/bin/env python3
"""
Jina News Scraper for Big Brain Ape Trading Bot
Uses Jina Reader API (r.jina.ai) to fetch financial news from Yahoo Finance.
Free, no API key required for the reader endpoint.

Sources:
  - Yahoo SPY page (broad market news + trending tickers with live prices)
  - Yahoo BTC-USD page (crypto-specific news)
  - Yahoo GC=F page (gold/commodity news)
  - CNBC Economy page (Fed/policy news)

Output: JSON with categorized headlines + trending tickers, saved to ~/.hermes/scripts/news-data/
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

OUTPUT_DIR = os.path.expanduser("~/.hermes/scripts/news-data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "latest-news.json")

# Yahoo Finance pages that return rich news feeds via Jina
SOURCES = {
    "market": "https://finance.yahoo.com/quote/SPY",
    "crypto": "https://finance.yahoo.com/quote/BTC-USD",
    "gold": "https://finance.yahoo.com/quote/GC=F",
    "fed_economy": "https://www.cnbc.com/economy/",
}

# Keywords for categorization
CATEGORIES = {
    "fed": ["fed", "fomc", "interest rate", "rate cut", "rate hike", "powell", "warsh", "central bank", "monetary policy", "balance sheet", "quantitative"],
    "inflation": ["cpi", "inflation", "core cpi", "pce", "price index", "deflation"],
    "geopolitics": ["iran", "hormuz", "war", "sanctions", "nato", "trump", "tariff", "trade war", "geopolitical", "oceania", "china", "russia", "ukraine", "israel", "gaza"],
    "oil": ["oil", "brent", "crude", "wti", "opec", "energy", "gas prices", "gasoline", "strait of hormuz"],
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "stablecoin", "defi", "token", "coinbase", "etf", "blockchain"],
    "gold": ["gold", "precious metal", "silver", "safe haven", "dedollarization", "central bank buying"],
    "tech": ["nvidia", "nvda", "apple", "aapl", "microsoft", "msft", "google", "googl", "amazon", "amzn", "meta", "tesla", "tsla", "ai", "chip", "semiconductor", "asml", "micron", "mu", "amd", "tsmc", "tsm", "sk hynix", "ibm"],
    "earnings": ["earnings", "quarterly", "q1", "q2", "q3", "q4", "revenue", "eps", "guidance", "beat", "miss"],
    "banks": ["jpmorgan", "goldman", "bank", "financial", "banking", "morgan stanley", "wells fargo", "citigroup"],
    "liquidity": ["m2", "money supply", "liquidity", "credit", "yield", "treasury", "bond", "spread"],
}

def fetch_url(url, timeout=30):
    """Fetch URL content via Jina Reader API."""
    try:
        cmd = [
            "curl", "-s", "--max-time", str(timeout),
            "https://r.jina.ai/",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"url": url})
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return result.stdout if result.returncode == 0 else ""
    except Exception as e:
        return f"[ERROR fetching {url}: {e}]"

def extract_headlines(content):
    """Extract numbered news headlines from Yahoo Finance page content."""
    headlines = []
    # Pattern: "1.   [News • 13 hours ago Headline text](url)"
    # or: "17.   [Breaking News • 2 days ago Headline text](url)"
    pattern = r'(\d+)\.\s+\[(Breaking News|News)\s+•\s+(.+?)\]\((https?://[^\)]+)\)'
    
    for match in re.finditer(pattern, content):
        num, news_type, time_and_headline, url = match.groups()
        # Split time and headline - format: "X hours ago Headline text" or "yesterday Headline" or "X days ago Headline"
        time_match = re.match(r'((?:\d+\s+(?:hours?|days?|minutes?)\s+ago)|(?:yesterday))\s+(.+)', time_and_headline)
        if time_match:
            time_str, headline = time_match.groups()
        else:
            time_str = "unknown"
            headline = time_and_headline
        
        headlines.append({
            "type": news_type,
            "time": time_str.strip(),
            "headline": headline.strip(),
            "url": url.strip(),
        })
    
    return headlines

def extract_trending_tickers(content):
    """Extract trending tickers with prices from Yahoo Finance page."""
    tickers = []
    # Pattern: "*   T TSM 419.48 (-0.22%)" or "*   S SNDK 1615.00 (-8.12%)"
    pattern = r'\*\s+([A-Z])\s+([A-Z]+)\s+([\d,]+\.?\d*)\s+\(([+-]?[\d.]+)%\)'
    
    for match in re.finditer(pattern, content):
        letter, symbol, price, change_pct = match.groups()
        tickers.append({
            "symbol": symbol,
            "price": float(price.replace(",", "")),
            "change_pct": float(change_pct),
        })
    
    return tickers

def categorize_headline(headline_text):
    """Categorize a headline based on keyword matching."""
    text_lower = headline_text.lower()
    categories = []
    for cat, keywords in CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            categories.append(cat)
    return categories if categories else ["other"]

def deduplicate(headlines):
    """Remove duplicate headlines (same headline text)."""
    seen = set()
    unique = []
    for h in headlines:
        key = h["headline"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_headlines = []
    trending_tickers = []
    source_status = {}
    
    for source_name, url in SOURCES.items():
        content = fetch_url(url)
        if not content or content.startswith("[ERROR"):
            source_status[source_name] = "failed"
            continue
        
        source_status[source_name] = "ok"
        
        # Extract headlines (Yahoo pages)
        if "yahoo" in url:
            headlines = extract_headlines(content)
            for h in headlines:
                h["source"] = source_name
                h["categories"] = categorize_headline(h["headline"])
            all_headlines.extend(headlines)
            
            # Extract trending tickers (only from market source to avoid dupes)
            if source_name == "market":
                trending_tickers = extract_trending_tickers(content)
        
        # Small delay to be polite
        time.sleep(1)
    
    # Deduplicate
    all_headlines = deduplicate(all_headlines)
    
    # Sort by implied recency (Breaking News first, then by position number)
    all_headlines.sort(key=lambda h: (0 if h["type"] == "Breaking News" else 1))
    
    # Group by category
    by_category = {}
    for h in all_headlines:
        for cat in h["categories"]:
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(h["headline"])
    
    # Build output
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": source_status,
        "total_headlines": len(all_headlines),
        "trending_tickers": trending_tickers,
        "headlines": all_headlines,
        "by_category": by_category,
    }
    
    # Save to file
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    
    # Print summary to stdout for cron consumption
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] Jina News Scraper")
    print(f"Sources: {json.dumps(source_status)}")
    print(f"Total headlines: {len(all_headlines)}")
    print(f"Trending tickers: {len(trending_tickers)}")
    print()
    print("--- TRENDING TICKERS ---")
    for t in trending_tickers[:10]:
        emoji = "🟢" if t["change_pct"] > 0 else "🔴"
        print(f"  {emoji} {t['symbol']} ${t['price']} ({t['change_pct']:+.2f}%)")
    print()
    print("--- BREAKING NEWS ---")
    for h in all_headlines:
        if h["type"] == "Breaking News":
            print(f"  🚨 [{h['time']}] {h['headline']}")
    print()
    print("--- BY CATEGORY ---")
    for cat in ["fed", "inflation", "geopolitics", "oil", "crypto", "gold", "tech", "earnings", "banks", "liquidity"]:
        if cat in by_category:
            print(f"  [{cat.upper()}] ({len(by_category[cat])} headlines)")
            for headline in by_category[cat][:5]:
                print(f"    • {headline}")
            if len(by_category[cat]) > 5:
                print(f"    ... and {len(by_category[cat]) - 5} more")
            print()
    print()
    print(f"Full data saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
