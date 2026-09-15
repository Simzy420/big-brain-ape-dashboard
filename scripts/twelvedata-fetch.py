#!/usr/bin/env python3
"""
Twelve Data Fetcher — FREE (800 calls/day, 8/min, no card needed)
Specializes in time series data for technical analysis.
Complements Finnhub (which does real-time quotes + news well but lacks chart history).

Usage:
    python3 twelvedata-fetch.py                    # All stock quotes with 52wk range
    python3 twelvedata-fetch.py --quote NVDA       # Single quote with 52wk range
    python3 twelvedata-fetch.py --series NVDA      # Daily OHLCV (20 bars) for chart reading
    python3 twelvedata-fetch.py --series BTC       # BTC daily bars
    python3 twelvedata-fetch.py --series EUR       # EUR/USD daily bars
"""

import json
import sys
import time
import argparse
import subprocess
from datetime import datetime, timezone

TD_KEY = "eeb30f15647e4a68af4c457965ff045f"
BASE_URL = "https://api.twelvedata.com"

# Stocks tradeable as xyz: perps
STOCK_PERPS = ["NVDA", "META", "GOOGL", "AAPL", "MSFT", "AMZN", "AMD", "INTC",
               "PLTR", "NFLX", "ORCL", "TSM", "COIN", "HOOD", "MSTR", "TSLA",
               "RIVN", "BABA", "GME", "COST", "LLY", "HIMS", "DKNG", "MU", "SNDK"]

# Asset symbol mapping (Twelve Data format)
SYMBOL_MAP = {
    "BTC": "BTC/USD", "ETH": "ETH/USD", "SOL": "SOL/USD",
    "EUR": "EUR/USD", "JPY": "USD/JPY",
    "GOLD": "XAU/USD", "SILVER": "XAG/USD",
    "BRENTOIL": "BRENT/USD", "CL": "WTI/USD",
}


def td_get(endpoint, params=None):
    """Make a Twelve Data API call via curl."""
    params = params or {}
    params["apikey"] = TD_KEY
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/{endpoint}?{query}"
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        return json.loads(result.stdout) if result.stdout else {}
    except Exception as e:
        return {"error": str(e)}


def fetch_quote(symbol):
    """Fetch quote with 52-week range (Twelve Data's edge over Finnhub)."""
    td_sym = SYMBOL_MAP.get(symbol, symbol)
    data = td_get("quote", {"symbol": td_sym})
    if "error" in data or "status" in data and data.get("status") == "error":
        return None
    return data


def fetch_all_quotes():
    """Fetch quotes for all stock perps with 52-week ranges."""
    print(f"{'='*90}")
    print(f"STOCK PERP QUOTES (with 52-week range) — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Source: Twelve Data (FREE, 800 calls/day)")
    print(f"{'='*90}")
    print(f"{'Symbol':<8} {'Price':>10} {'Change%':>9} {'52W Low':>10} {'52W High':>10} {'% of Range':>11}")
    print("-" * 90)

    count = 0
    for sym in STOCK_PERPS:
        q = fetch_quote(sym)
        if q and q.get("close"):
            close = float(q["close"])
            pct = q.get("percent_change", "0")
            wk = q.get("fifty_two_week", {})
            low = float(wk.get("low", 0))
            high = float(wk.get("high", 0))
            range_pct = ((close - low) / (high - low) * 100) if high > low else 0
            print(f"{sym:<8} ${close:>9.2f} {float(pct):>+8.2f}% ${low:>9.2f} ${high:>9.2f} {range_pct:>10.1f}%")
            count += 1
        else:
            print(f"{sym:<8} {'N/A':>10}")
        # Rate limit: 8/min → wait ~8 seconds between calls
        if sym != STOCK_PERPS[-1]:
            time.sleep(8)

    print(f"\n{count}/{len(STOCK_PERPS)} quotes fetched. Zero cost.")


def fetch_series(symbol, interval="1day", outputsize=20):
    """Fetch daily OHLCV time series for technical analysis / chart reading."""
    td_sym = SYMBOL_MAP.get(symbol, symbol)
    data = td_get("time_series", {
        "symbol": td_sym, "interval": interval, "outputsize": outputsize,
        "format": "JSON"
    })
    if "error" in data or "status" in data and data.get("status") == "error":
        print(f"❌ Error fetching {symbol}: {data.get('message', data)}")
        return

    values = data.get("values", [])
    if not values:
        print(f"❌ No data for {symbol}")
        return

    print(f"\n📈 {symbol} ({td_sym}) — Daily OHLCV, last {len(values)} bars")
    print(f"   Source: Twelve Data (FREE)")
    print(f"   {'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>14}")
    print("   " + "-" * 78)
    for v in reversed(values):
        vol = v.get("volume", "N/A")
        vol_str = f"{int(vol):,}" if vol and vol != "N/A" else "N/A"
        print(f"   {v['datetime']:<12} ${float(v['open']):>9.2f} ${float(v['high']):>9.2f} ${float(v['low']):>9.2f} ${float(v['close']):>9.2f} {vol_str:>13}")

    # Simple technical summary
    closes = [float(v["close"]) for v in values]
    if len(closes) >= 2:
        recent = closes[0]
        prior = closes[-1]
        move = ((recent - prior) / prior) * 100
        high_20 = max(float(v["high"]) for v in values)
        low_20 = min(float(v["low"]) for v in values)
        print(f"\n   📊 20-bar range: ${low_20:.2f} - ${high_20:.2f}")
        print(f"   📊 Period change: {move:+.2f}%")
        print(f"   📊 Current close: ${recent:.2f} ({((recent-low_20)/(high_20-low_20)*100):.1f}% of range)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Twelve Data Fetcher (FREE)")
    parser.add_argument("--quote", type=str, help="Single quote with 52wk range")
    parser.add_argument("--series", type=str, help="Daily OHLCV time series for chart reading")
    parser.add_argument("--all", action="store_true", help="All stock quotes with 52wk range")
    args = parser.parse_args()

    if args.quote:
        q = fetch_quote(args.quote)
        if q and q.get("close"):
            print(f"\n📈 {args.quote}: ${q['close']} ({q.get('percent_change','?')}%)")
            wk = q.get("fifty_two_week", {})
            print(f"   52W Range: ${wk.get('low','?')} - ${wk.get('high','?')}")
    elif args.series:
        fetch_series(args.series)
    else:
        fetch_all_quotes()
