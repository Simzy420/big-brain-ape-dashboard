#!/usr/bin/env python3
"""
Master keyless API aggregator for Druckenmiller trading agent.
All endpoints are 100% free, no API key required, no signup needed.
These augment CoinGecko + Alpha Vantage + Firecrawl — they don't replace them.

Data sources:
  - Frankfurter (ECB)      : Forex / exchange rates
  - Binance Public         : Crypto prices + perpetual funding rates
  - CoinPaprika            : Crypto prices (redundancy / cross-check)
  - Blockchain.com         : Bitcoin network stats (hash rate, block time)
  - mempool.space          : Bitcoin mempool fees (on-chain activity gauge)
  - DeFiLlama Protocols    : DeFi TVL by protocol (liquidity flows)
  - DeFiLlama Stablecoins  : Total stablecoin market cap (liquidity proxy)
  - DeFiLlama Yields       : DeFi yield pools (where capital is hunting return)
  - Fear & Greed (alt.me)  : Crypto sentiment index

Usage:
    python3 keyless-data-fetch.py                    # Full macro dashboard
    python3 keyless-data-fetch.py --fx               # Just forex rates
    python3 keyless-data-fetch.py --funding          # Just perp funding rates
    python3 keyless-data-fetch.py --defi             # Just DeFi liquidity
    python3 keyless-data-fetch.py --sentiment        # Just Fear & Greed
    python3 keyless-data-fetch.py --btc-network      # Just BTC network stats
"""

import json
import sys
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_json(url, timeout=15):
    """Fetch JSON from a URL with error handling."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except urllib.error.URLError as e:
        return {"_error": f"URL error: {e.reason}"}
    except Exception as e:
        return {"_error": str(e)}


def post_json(url, payload, timeout=15):
    """POST JSON to a URL."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={**HEADERS, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"_error": str(e)}


# ─────────────────────────────────────────────
# FOREX (Frankfurter / ECB)
# ─────────────────────────────────────────────
def fetch_forex():
    """Fetch USD exchange rates from ECB via Frankfurter."""
    data = fetch_json("https://api.frankfurter.app/latest?from=USD&to=EUR,JPY,GBP,CHF,CAD,AUD,CNY,MXN")
    if "_error" in data:
        print(f"❌ Frankfurter: {data['_error']}")
        return

    print("\n💵 FOREX RATES (ECB / Frankfurter)")
    print(f"   Base: USD | Date: {data.get('date', '?')}")
    print(f"   {'Pair':<12} {'Rate':>10}")
    print(f"   {'-'*24}")
    for curr, rate in sorted(data.get("rates", {}).items()):
        print(f"   USD/{curr:<8} {rate:>10.5f}")


# ─────────────────────────────────────────────
# CRYPTO PRICES + FUNDING (Binance)
# ─────────────────────────────────────────────
def fetch_binance_prices():
    """Fetch crypto prices from Binance public API."""
    symbols = '["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","LTCUSDT"]'
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbols={symbols}"
    data = fetch_json(url)
    if "_error" in data:
        print(f"❌ Binance: {data['_error']}")
        return

    print("\n📈 CRYPTO PRICES (Binance Public)")
    print(f"   {'Symbol':<12} {'Price':>12} {'24h%':>8} {'Volume':>16}")
    print(f"   {'-'*52}")
    for d in data:
        sym = d["symbol"].replace("USDT", "")
        price = float(d["lastPrice"])
        change = float(d["priceChangePercent"])
        vol = float(d["quoteVolume"])
        print(f"   {sym:<12} ${price:>11,.2f} {change:>7.2f}% ${vol:>14,.0f}")


def fetch_funding_rates():
    """Fetch perpetual futures funding rates from Binance."""
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
    print("\n💰 PERPETUAL FUNDING RATES (Binance Futures)")
    print(f"   {'Symbol':<12} {'Mark Price':>12} {'Funding Rate':>14} {'Annualized':>12}")
    print(f"   {'-'*54}")

    for sym in symbols:
        data = fetch_json(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}")
        if "_error" in data:
            print(f"   {sym:<12} Error: {data['_error'][:30]}")
            continue

        mark = float(data.get("markPrice", 0))
        funding = float(data.get("lastFundingRate", 0))
        # Annualized = funding * 3 (8h funding) * 365
        annual = funding * 3 * 365 * 100
        print(f"   {sym.replace('USDT',''):<12} ${mark:>11,.2f} {funding*100:>13.6f}% {annual:>10.2f}%")
        time.sleep(0.3)  # light rate limiting


# ─────────────────────────────────────────────
# DEFI LIQUIDITY (DeFiLlama)
# ─────────────────────────────────────────────
def fetch_defi_tvl():
    """Fetch top DeFi protocols by TVL."""
    data = fetch_json("https://api.llama.fi/protocols")
    if "_error" in data:
        print(f"❌ DeFiLlama: {data['_error']}")
        return

    # Filter to actual DeFi protocols (not CEXs)
    defi_protos = [p for p in data if (p.get("tvl") or 0) > 0 and "CEX" not in str(p.get("parentProtocol", ""))]
    top = sorted(defi_protos, key=lambda x: (x.get("tvl") or 0), reverse=True)[:15]

    print("\n🏦 DEFI TVL — Top 15 Protocols (DeFiLlama)")
    print(f"   {'#':<4} {'Protocol':<22} {'TVL':>14} {'Chain':<16}")
    print(f"   {'-'*60}")
    for i, p in enumerate(top, 1):
        tvl = p.get("tvl", 0)
        chain = p.get("chain", "?")
        print(f"   {i:<4} {p['name']:<22} ${tvl/1e9:>12.2f}B {chain:<16}")


def fetch_stablecoin_cap():
    """Fetch total stablecoin market cap — key liquidity proxy."""
    data = fetch_json("https://stablecoins.llama.fi/stablecoincharts/all")
    if "_error" in data:
        print(f"❌ DeFiLlama Stablecoins: {data['_error']}")
        return

    if not data:
        print("   No data")
        return

    latest = data[-1]
    prev = data[-8] if len(data) >= 8 else data[0]  # ~7 days ago

    total = latest.get("totalCirculating", {}).get("peggedUSD", 0)
    prev_total = prev.get("totalCirculating", {}).get("peggedUSD", 0)
    change = ((total - prev_total) / prev_total * 100) if prev_total else 0

    print("\n💉 STABLECOIN MARKET CAP (DeFiLlama)")
    print(f"   Total: ${total/1e9:.2f}B")
    print(f"   7-day change: {change:+.2f}%")

    # Breakdown by token
    breakdown = latest.get("totalCirculating", {})
    tokens = {k: v for k, v in breakdown.items() if k != "peggedUSD" and isinstance(v, dict)}
    if tokens:
        print(f"   Breakdown:")
        for token, info in sorted(tokens.items(), key=lambda x: x[1].get("peggedUSD", 0), reverse=True)[:5]:
            cap = info.get("peggedUSD", 0)
            if cap > 0:
                print(f"     {token}: ${cap/1e9:.2f}B")


def fetch_defi_yields():
    """Fetch top DeFi yield pools — shows where capital is hunting return."""
    data = fetch_json("https://yields.llama.fi/pools", timeout=20)
    if "_error" in data:
        print(f"❌ DeFiLlama Yields: {data['_error']}")
        return

    pools = data.get("data", [])
    # Filter: TVL > $50M, APY > 0
    big_pools = [p for p in pools if p.get("tvlUsd", 0) > 50e6 and p.get("apy", 0) > 0]
    top = sorted(big_pools, key=lambda x: x.get("tvlUsd", 0), reverse=True)[:10]

    print("\n🌾 DEFI YIELD POOLS — Top 10 by TVL (DeFiLlama)")
    print(f"   {'Project':<20} {'Symbol':<12} {'APY':>8} {'TVL':>12}")
    print(f"   {'-'*56}")
    for p in top:
        print(f"   {p.get('project','?'):<20} {p.get('symbol','?'):<12} {p.get('apy',0):>7.1f}% ${p.get('tvlUsd',0)/1e6:>10.0f}M")

    # Average APY of top pools — high = risk-on, low = risk-off
    avg_apy = sum(p.get("apy", 0) for p in top) / len(top) if top else 0
    print(f"\n   Avg APY (top 10): {avg_apy:.1f}% — {'Risk-on (capital chasing yield)' if avg_apy > 5 else 'Risk-off (capital defensive)'}")


# ─────────────────────────────────────────────
# SENTIMENT (Fear & Greed)
# ─────────────────────────────────────────────
def fetch_fear_greed():
    """Fetch crypto Fear & Greed Index."""
    data = fetch_json("https://api.alternative.me/fng/?limit=7")
    if "_error" in data:
        print(f"❌ Fear & Greed: {data['_error']}")
        return

    items = data.get("data", [])
    print("\n😨 CRYPTO FEAR & GREED INDEX (Alternative.me)")
    print(f"   {'Date':<12} {'Value':>6} {'Classification'}")
    print(f"   {'-'*36}")

    for item in items:
        ts = int(item["timestamp"])
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        val = item["value"]
        cls = item["value_classification"]
        print(f"   {date:<12} {val:>6} {cls}")


# ─────────────────────────────────────────────
# BITCOIN NETWORK (Blockchain.com + mempool.space)
# ─────────────────────────────────────────────
def fetch_btc_network():
    """Fetch Bitcoin network stats — hash rate, block time, mempool fees."""
    # Blockchain.com stats
    bc = fetch_json("https://api.blockchain.info/stats")
    # mempool.space fees
    mp = fetch_json("https://mempool.space/api/v1/fees/recommended")

    print("\n⛏️ BITCOIN NETWORK STATS")
    print(f"   {'-'*40}")

    if "_error" not in bc:
        print(f"   Hash Rate:        {bc.get('hash_rate', 0)/1e9:,.0f} GH/s")
        print(f"   Block time:       {bc.get('minutes_between_blocks', 0):.1f} min")
        print(f"   Blocks mined (24h): {bc.get('n_blocks_mined', '?')}")
        print(f"   Total BTC supply: {bc.get('totalbc', 0)/1e8:,.0f} BTC")

    if "_error" not in mp:
        print(f"   Mempool fees:")
        print(f"     Fastest:        {mp.get('fastestFee', '?')} sat/vB")
        print(f"     Half hour:      {mp.get('halfHourFee', '?')} sat/vB")
        print(f"     Hour:           {mp.get('hourFee', '?')} sat/vB")

    # Interpretation
    fastest = mp.get("fastestFee", 0) if "_error" not in mp else 0
    if fastest > 50:
        print(f"   → High on-chain activity (fees elevated)")
    elif fastest > 10:
        print(f"   → Moderate on-chain activity")
    else:
        print(f"   → Low on-chain activity (fees minimal)")


# ─────────────────────────────────────────────
# COINPAPRIKA (Cross-check prices)
# ─────────────────────────────────────────────
def fetch_coinpaprika():
    """Fetch crypto prices from CoinPaprika as cross-check."""
    data = fetch_json("https://api.coinpaprika.com/v1/tickers?limit=10")
    if "_error" in data:
        print(f"❌ CoinPaprika: {data['_error']}")
        return

    print("\n🔍 CRYPTO CROSS-CHECK (CoinPaprika)")
    print(f"   {'Symbol':<12} {'Price':>12} {'24h%':>8} {'Mkt Cap':>14}")
    print(f"   {'-'*50}")
    for d in data:
        sym = d["symbol"]
        quotes = d.get("quotes", {}).get("USD", {})
        price = quotes.get("price", 0)
        change = quotes.get("percent_change_24h", 0)
        mcap = quotes.get("market_cap", 0)
        print(f"   {sym:<12} ${price:>11,.2f} {change:>7.2f}% ${mcap/1e9:>12.2f}B")


# ─────────────────────────────────────────────
# FULL MACRO DASHBOARD
# ─────────────────────────────────────────────
def fetch_full_dashboard():
    """Run all keyless data sources for a complete macro picture."""
    now = datetime.now(timezone.utc)
    print("=" * 60)
    print(f"MACRO DATA DASHBOARD — {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"All data via free keyless APIs — Zero Firecrawl credits")
    print("=" * 60)

    fetch_fear_greed()
    fetch_binance_prices()
    fetch_funding_rates()
    fetch_forex()
    fetch_defi_tvl()
    fetch_stablecoin_cap()
    fetch_defi_yields()
    fetch_btc_network()

    print("\n" + "=" * 60)
    print("Dashboard complete. All sources: free, keyless, no signup.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Keyless Market Data Aggregator")
    parser.add_argument("--fx", action="store_true", help="Forex rates only")
    parser.add_argument("--funding", action="store_true", help="Perp funding rates only")
    parser.add_argument("--defi", action="store_true", help="DeFi TVL + stablecoins + yields")
    parser.add_argument("--sentiment", action="store_true", help="Fear & Greed only")
    parser.add_argument("--btc-network", action="store_true", help="BTC network stats only")
    parser.add_argument("--cross-check", action="store_true", help="CoinPaprika cross-check")
    parser.add_argument("--all", action="store_true", help="Full macro dashboard")

    args = parser.parse_args()

    if args.fx:
        fetch_forex()
    elif args.funding:
        fetch_funding_rates()
    elif args.defi:
        fetch_defi_tvl()
        fetch_stablecoin_cap()
        fetch_defi_yields()
    elif args.sentiment:
        fetch_fear_greed()
    elif args.btc_network:
        fetch_btc_network()
    elif args.cross_check:
        fetch_coinpaprika()
    elif args.all:
        fetch_full_dashboard()
    else:
        fetch_full_dashboard()
