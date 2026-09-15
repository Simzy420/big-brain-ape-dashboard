#!/usr/bin/env python3.11
"""
Big Brain Ape — Autonomous Campaign Generator + X Poster
Calls Campaign Studio API to generate marketing content,
picks the best copy variant, formats as a tweet, posts to X.
Runs daily via cron. Zero human involvement.
"""
import json, urllib.request, subprocess, random, sys, time, os

# ============================================================
# CONFIG
# ============================================================
STUDIO_URL = "https://simzy-campaign-studio.hf.space/api/generate"
XURL_PATH = "/home/hermes/.hermes/home/.local/bin/xurl"

# Rotating campaign briefs — different angle each day
BRIEFS = [
    {
        "brief": "Promote Big Brain Ape autonomous trading bot to crypto traders tired of staring at charts all day",
        "audience": "Crypto traders, 25-45",
        "product": "Big Brain Ape — autonomous AI trading agent for Hyperliquid perps, 98 assets, 3-5x leverage, Druckenmiller macro strategy",
        "tone": "bold",
        "channels": ["social"]
    },
    {
        "brief": "Market Big Brain Ape as the solution for busy professionals who want to trade but have no time",
        "audience": "Busy professionals interested in crypto",
        "product": "Big Brain Ape — 100% autonomous AI trading agent. Trades while you work, sleep, live. If it doesn't make money, it's free.",
        "tone": "professional",
        "channels": ["social"]
    },
    {
        "brief": "Highlight that Big Brain Ape trades 98 assets including stocks, gold, crypto, and indices — not just Bitcoin",
        "audience": "Diversified investors and traders",
        "product": "Big Brain Ape trades NVDA, TSLA, GOLD, BTC, ETH, SP500 and 93 more assets on Hyperliquid perps. One AI agent, full market coverage.",
        "tone": "informative",
        "channels": ["social"]
    },
    {
        "brief": "Push the risk-free offer: if Big Brain Ape doesn't make money, the service is free",
        "audience": "Skeptical retail investors",
        "product": "Big Brain Ape — autonomous trading with a performance guarantee. Doesn't make money = you don't pay. Druckenmiller-style macro strategy, 98 assets.",
        "tone": "confident",
        "channels": ["social"]
    },
    {
        "brief": "Tease the Druckenmiller strategy — trade like a legend without needing 30 years of experience",
        "audience": "Aspiring traders who follow macro legends",
        "product": "Big Brain Ape uses a Druckenmiller-inspired macro strategy: liquidity flows, central bank policy, regime shifts. 98 assets, 3-5x leverage, fully autonomous.",
        "tone": "bold",
        "channels": ["social"]
    },
    {
        "brief": "Promote the free stock and crypto analysis available at the Telegram bot",
        "audience": "Retail investors wanting quick analysis",
        "product": "Big Brain Ape Telegram bot — free stock and crypto analysis. Type any ticker, get instant analysis. Hire the full autonomous trading agent for managed trading.",
        "tone": "friendly",
        "channels": ["social"]
    },
    {
        "brief": "Show off the trading dashboard with live positions, charts, and macro data",
        "audience": "Tech-savvy investors who like data dashboards",
        "product": "Big Brain Ape dashboard — live trading positions, crypto whale activity, Fear & Greed index, analyst ratings, support/resistance levels. Plus autonomous trading across 98 assets.",
        "tone": "informative",
        "channels": ["social"]
    },
]

# Hashtag pool — rotate to avoid repetition
HASHTAGS = [
    "#CryptoTrading #AutonomousAI #Hyperliquid #TradingBot",
    "#AI #Trading #Crypto #Investing #Fintech",
    "#MacroTrading #Druckenmiller #Perps #DeFi",
    "#StockMarket #Crypto #AI #TradingAgent #Wealth",
    "#AltCoins #Bitcoin #Ethereum #AI #Automation",
    "#TradingBot #CryptoAI #PassiveIncome #Investing",
    "#Fintech #AI #DeFi #Trading #Hyperliquid",
]

CTA = "Try the beta free → simzy420.github.io/big-brain-ape-dashboard"

# ============================================================
# STEP 1: Generate campaign via Campaign Studio API
# ============================================================

brief = random.choice(BRIEFS)
print(f"Selected brief: {brief['brief'][:60]}...")

payload = json.dumps(brief).encode()
req = urllib.request.Request(
    STUDIO_URL,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    resp = urllib.request.urlopen(req, timeout=90)
    result = json.loads(resp.read())
    print("✅ Campaign generated successfully")
except Exception as e:
    print(f"❌ Campaign Studio API failed: {e}")
    sys.exit(0)  # Exit 0 so cron doesn't show error

# ============================================================
# STEP 2: Pick the best copy variant and format as tweet
# ============================================================

variants = result.get("copy_variants", [])
if not variants:
    print("❌ No copy variants returned")
    sys.exit(0)

# Pick the variant with the punchiest headline (shortest = punchiest)
best = min(variants, key=lambda v: len(v.get("headline", "")))
headline = best.get("headline", "").strip()
body = best.get("body", "").strip()

hashtags = random.choice(HASHTAGS)

# Build tweet — keep under 280 chars
tweet = f"{headline}\n\n{body}\n\n{hashtags}\n\n{CTA}"

# If too long, trim the body
if len(tweet) > 275:
    max_body = 275 - len(headline) - len(hashtags) - len(CTA) - 8
    if max_body > 50:
        body = body[:max_body-3] + "..."
        tweet = f"{headline}\n\n{body}\n\n{hashtags}\n\n{CTA}"
    else:
        # Just use headline + hashtags + CTA
        tweet = f"{headline}\n\n{hashtags}\n\n{CTA}"

print(f"\n=== TWEET ({len(tweet)} chars) ===")
print(tweet)
print("=" * 40)

# ============================================================
# STEP 3: Post to X via xurl
# ============================================================

try:
    post_result = subprocess.run(
        [XURL_PATH, "post", tweet],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PATH": os.path.expanduser("~/.hermes/home/.npm-global/bin") + ":" + os.environ.get("PATH","")}
    )
    output = post_result.stdout + post_result.stderr
    print(f"X post result: {output[:500]}")
    
    if post_result.returncode == 0:
        print("✅ Posted to X successfully")
    else:
        print(f"⚠️ X post returned code {post_result.returncode}")
except Exception as e:
    print(f"❌ Failed to post to X: {e}")

# Exit 0 always — cron must not show errors
sys.exit(0)
