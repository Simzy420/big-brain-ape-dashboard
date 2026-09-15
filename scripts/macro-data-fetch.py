#!/usr/bin/env python3
"""
Macro Liquidity & Sentiment Data Fetcher — FREE, no API keys needed.

Sources:
  - Hyperliquid API (no key): Funding rates, open interest, mark/oracle prices for ALL perps
  - alternative.me (no key): Crypto Fear & Greed Index
  - DeFiLlama (no key): Stablecoin market cap, flows, dominance
  - FRED (key in memory): Treasury yield curve spreads (10Y-2Y, 10Y-3M)

Usage:
  python3 macro-data-fetch.py                     # Everything
  python3 macro-data-fetch.py --hl                # Hyperliquid funding + OI only
  python3 macro-data-fetch.py --fng               # Crypto Fear & Greed only
  python3 macro-data-fetch.py --stable            # Stablecoin flows only
  python3 macro-data-fetch.py --yield             # Treasury yield curve only
  python3 macro-data-fetch.py --hl-symbols BTC ETH SOL  # Specific HL perps
"""

import json
import sys
import time
import argparse
import subprocess
from datetime import datetime, timezone, timedelta

FRED_KEY = "d53def445cd7907e68953b2c2974f0b4"
HL_API = "https://api.hyperliquid.xyz/info"
FNG_API = "https://api.alternative.me/fng/"
DEFILLAMA_STABLECOINS = "https://stablecoins.llama.fi/stablecoins"
DEFILLAMA_CHARTS = "https://stablecoins.llama.fi/stablecoincharts/all"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# The 98 assets we trade (for HL filtering)
TRADEABLE_CRYPTO = [
    "BTC", "ETH", "SOL", "AVAX", "BNB", "LTC", "LINK", "DOGE", "XRP", "ADA",
    "DOT", "UNI", "AAVE", "TAO", "FET", "RENDER", "NEAR", "HYPE", "VIRTUAL",
    "KAITO", "TRX", "ZRO", "JTO", "APT", "XLM", "ETHFI", "HBAR", "SUI", "ARB",
    "OP", "CRV", "LDO", "SEI", "WLD", "TIA", "ENA", "AR", "WIF", "FARTCOIN",
    "MORPHO", "TRUMP", "PENGU", "PAXG", "PUMP", "XPL", "ZEC", "LIT", "XMR",
    "IP", "ASTER", "CC", "VVV", "SKY", "MON", "BCH", "FTT", "TON", "WLFI",
    "AERO", "ONDO",
]


def post_json(url, body):
    """POST JSON to an API and return parsed response."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=20
        )
        return json.loads(result.stdout) if result.stdout else {}
    except Exception as e:
        return {"error": str(e)}


def get_json(url):
    """GET from an API and return parsed response."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        return json.loads(result.stdout) if result.stdout else {}
    except Exception as e:
        return {"error": str(e)}


# ─── HYPERLIQUID FUNDING + OPEN INTEREST ───

def fetch_hl_funding(symbols=None):
    """Fetch funding rates, OI, mark/oracle for all Hyperliquid perps."""
    data = post_json(HL_API, {"type": "metaAndAssetCtxs"})
    if isinstance(data, dict) and "error" in data:
        return None
    if not isinstance(data, list) or len(data) < 2:
        return None

    meta, ctxs = data[0], data[1]
    results = []

    for asset, ctx in zip(meta.get("universe", []), ctxs):
        name = asset.get("name", "")
        funding = float(ctx.get("funding") or 0)
        oi = float(ctx.get("openInterest") or 0)
        mark = float(ctx.get("markPx") or 0)
        oracle = float(ctx.get("oraclePx") or 0)
        premium = float(ctx.get("premium") or 0)
        day_vol = float(ctx.get("dayNtlVlm") or 0)
        max_lev = asset.get("maxLeverage", "?")

        # Annualized funding
        annual_funding = funding * 24 * 365 * 100  # hourly -> annual %

        # Premium (mark vs oracle)
        premium_pct = ((mark - oracle) / oracle * 100) if oracle else 0

        # OI in USD
        oi_usd = oi * mark if mark > 0 else 0

        results.append({
            "symbol": name,
            "funding_hourly": funding * 100,
            "funding_annual": annual_funding,
            "open_interest": oi,
            "oi_usd": oi_usd,
            "mark_price": mark,
            "oracle_price": oracle,
            "premium_pct": premium_pct,
            "day_volume_usd": day_vol,
            "max_leverage": max_lev,
        })

    # Filter to specific symbols if requested
    if symbols:
        results = [r for r in results if r["symbol"] in symbols]

    return results


def print_hl_funding(symbols=None):
    """Print Hyperliquid funding data in formatted output."""
    results = fetch_hl_funding(symbols)
    if not results:
        print("Failed to fetch Hyperliquid data")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*100}")
    print(f"HYPERLIQUID FUNDING & OPEN INTEREST — {now}")
    print(f"Source: Hyperliquid API (FREE, no key)")
    print(f"{'='*100}")

    # Sort by absolute funding rate (most extreme first)
    results.sort(key=lambda x: abs(x["funding_annual"]), reverse=True)

    # Top 20 by OI if no filter, otherwise all matching
    if not symbols:
        display = sorted(results, key=lambda x: x["oi_usd"], reverse=True)[:25]
        print(f"\nTop 25 by Open Interest ($USD):")
    else:
        display = results
        print(f"\nRequested symbols:")

    print(f"\n{'Symbol':<12} {'Fund%/hr':>10} {'Fund%/yr':>10} {'OI ($)':>14} {'Mark':>12} {'Premium%':>10} {'MaxLev':>7}")
    print("-" * 100)
    for r in display:
        print(f"{r['symbol']:<12} {r['funding_hourly']:>+9.4f}% {r['funding_annual']:>+9.1f}% ${r['oi_usd']/1e6:>11.1f}M ${r['mark_price']:>11.4f} {r['premium_pct']:>+9.4f}% {r['max_leverage']:>5}x")

    # Funding extremes
    print(f"\n--- FUNDING EXTREMES (annualized) ---")
    most_long = max(results, key=lambda x: x["funding_annual"])
    most_short = min(results, key=lambda x: x["funding_annual"])
    print(f"Most LONG funding:  {most_long['symbol']} at {most_long['funding_annual']:+.1f}%/yr (${most_long['oi_usd']/1e6:.1f}M OI)")
    print(f"Most SHORT funding: {most_short['symbol']} at {most_short['funding_annual']:+.1f}%/yr (${most_short['oi_usd']/1e6:.1f}M OI)")

    # Total OI
    total_oi = sum(r["oi_usd"] for r in results)
    total_vol = sum(r["day_volume_usd"] for r in results)
    print(f"\nTotal OI across all perps: ${total_oi/1e9:.2f}B")
    print(f"Total 24h volume:          ${total_vol/1e9:.2f}B")


# ─── CRYPTO FEAR & GREED INDEX ───

def fetch_fng(days=7):
    """Fetch Crypto Fear & Greed Index."""
    data = get_json(f"{FNG_API}?limit={days}")
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or "data" not in data:
        return None
    results = []
    for item in data["data"]:
        ts = int(item.get("timestamp", 0))
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        results.append({
            "date": date,
            "value": int(item.get("value", 0)),
            "classification": item.get("value_classification", ""),
        })
    return results


def print_fng():
    """Print Crypto Fear & Greed Index."""
    results = fetch_fng(7)
    if not results:
        print("Failed to fetch Fear & Greed Index")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"CRYPTO FEAR & GREED INDEX — {now}")
    print(f"Source: alternative.me (FREE, no key)")
    print(f"{'='*60}")

    latest = results[0]
    print(f"\nCurrent:    {latest['value']}/100 — {latest['classification'].upper()}")
    print(f"\n7-day trend:")
    for r in reversed(results):
        bar = "█" * (r["value"] // 5) + "░" * (20 - r["value"] // 5)
        print(f"  {r['date']}  {bar} {r['value']:>3} {r['classification']}")

    # Interpretation
    val = latest["value"]
    if val <= 25:
        print(f"\n⚠️  EXTREME FEAR — Historically a BUY zone for contrarians")
    elif val <= 45:
        print(f"\n📉 FEAR — Market cautious, potential accumulation zone")
    elif val <= 55:
        print(f"\n😐 NEUTRAL — No strong sentiment signal")
    elif val <= 75:
        print(f"\n📈 GREED — Market optimistic, trim risk")
    else:
        print(f"\n🔥 EXTREME GREED — Historically a SELL zone for contrarians")


# ─── STABLECOIN FLOWS (DeFiLlama) ───

def fetch_stablecoin_data():
    """Fetch stablecoin market cap, dominance, and recent flows."""
    # Current stablecoin data
    coins_data = get_json(DEFILLAMA_STABLECOINS)
    # Historical charts for flow calculation
    charts_data = get_json(DEFILLAMA_CHARTS)

    if isinstance(coins_data, dict) and "error" in coins_data:
        return None

    result = {
        "total_market_cap": 0,
        "top_coins": [],
        "flows_7d": None,
        "flows_30d": None,
    }

    # Per-coin circulating
    coins = coins_data.get("peggedAssets", [])
    total = 0
    for c in coins:
        circ = c.get("circulating", {})
        mc = circ.get("peggedUSD", 0) if isinstance(circ, dict) else 0
        prev_week = c.get("circulatingPrevWeek", {}).get("peggedUSD", 0) if isinstance(c.get("circulatingPrevWeek"), dict) else 0
        prev_month = c.get("circulatingPrevMonth", {}).get("peggedUSD", 0) if isinstance(c.get("circulatingPrevMonth"), dict) else 0

        if mc > 1e8:  # >100M
            week_change = ((mc - prev_week) / prev_week * 100) if prev_week else 0
            month_change = ((mc - prev_month) / prev_month * 100) if prev_month else 0
            result["top_coins"].append({
                "symbol": c.get("symbol", "?"),
                "name": c.get("name", "?"),
                "market_cap": mc,
                "week_change_pct": week_change,
                "month_change_pct": month_change,
            })
            total += mc

    result["total_market_cap"] = total
    result["top_coins"].sort(key=lambda x: x["market_cap"], reverse=True)

    # Historical flows
    if isinstance(charts_data, list) and len(charts_data) >= 30:
        latest = charts_data[-1]
        latest_mc = latest.get("totalCirculating", {}).get("peggedUSD", 0)

        if len(charts_data) >= 8:
            week_ago = charts_data[-8]
            week_ago_mc = week_ago.get("totalCirculating", {}).get("peggedUSD", 0)
            if week_ago_mc:
                result["flows_7d"] = {
                    "current": latest_mc,
                    "previous": week_ago_mc,
                    "change_usd": latest_mc - week_ago_mc,
                    "change_pct": (latest_mc - week_ago_mc) / week_ago_mc * 100,
                }

        if len(charts_data) >= 31:
            month_ago = charts_data[-31]
            month_ago_mc = month_ago.get("totalCirculating", {}).get("peggedUSD", 0)
            if month_ago_mc:
                result["flows_30d"] = {
                    "current": latest_mc,
                    "previous": month_ago_mc,
                    "change_usd": latest_mc - month_ago_mc,
                    "change_pct": (latest_mc - month_ago_mc) / month_ago_mc * 100,
                }

    return result


def print_stablecoins():
    """Print stablecoin flows data."""
    data = fetch_stablecoin_data()
    if not data:
        print("Failed to fetch stablecoin data")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*80}")
    print(f"STABLECOIN FLOWS — {now}")
    print(f"Source: DeFiLlama (FREE, no key)")
    print(f"{'='*80}")

    print(f"\nTotal Stablecoin Market Cap: ${data['total_market_cap']/1e9:.2f}B")

    # Flows
    if data["flows_7d"]:
        f7 = data["flows_7d"]
        direction = "INFLOW" if f7["change_usd"] > 0 else "OUTFLOW"
        print(f"\n7-Day Flow: {direction} ${abs(f7['change_usd'])/1e9:.2f}B ({f7['change_pct']:+.2f}%)")
    if data["flows_30d"]:
        f30 = data["flows_30d"]
        direction = "INFLOW" if f30["change_usd"] > 0 else "OUTFLOW"
        print(f"30-Day Flow: {direction} ${abs(f30['change_usd'])/1e9:.2f}B ({f30['change_pct']:+.2f}%)")

    # Top coins
    print(f"\nTop Stablecoins by Market Cap:")
    print(f"{'Symbol':<8} {'Name':<25} {'Market Cap':>12} {'7d Change':>10} {'30d Change':>11}")
    print("-" * 70)
    for c in data["top_coins"][:10]:
        print(f"{c['symbol']:<8} {c['name']:<25} ${c['market_cap']/1e9:>10.2f}B {c['week_change_pct']:>+9.2f}% {c['month_change_pct']:>+10.2f}%")

    # Interpretation
    if data["flows_7d"]:
        if f7["change_pct"] > 0.5:
            print(f"\n🟢 STABLECOIN INFLOW — Liquidity entering crypto (BULLISH)")
        elif f7["change_pct"] < -0.5:
            print(f"\n🔴 STABLECOIN OUTFLOW — Liquidity leaving crypto (BEARISH)")
        else:
            print(f"\n⚪ STABLECOIN FLAT — No significant liquidity shift")


# ─── TREASURY YIELD CURVE (FRED) ───

def fetch_yield_curve():
    """Fetch key yield curve spreads from FRED."""
    series = {
        "T10Y2Y": "10Y-2Y Spread",
        "T10Y3M": "10Y-3M Spread",
        "DGS10": "10Y Yield",
        "DGS2": "2Y Yield",
        "DGS30": "30Y Yield",
        "DGS3M": "3M Yield",
        "DFF": "Fed Funds Rate",
    }

    results = {}
    for series_id, name in series.items():
        url = f"{FRED_BASE}?series_id={series_id}&api_key={FRED_KEY}&file_type=json&limit=5&sort_order=desc"
        data = get_json(url)
        if isinstance(data, dict) and "observations" in data:
            obs = data["observations"]
            if obs:
                val = obs[0].get("value", ".")
                date = obs[0].get("date", "")
                if val != ".":
                    results[series_id] = {
                        "name": name,
                        "value": float(val),
                        "date": date,
                    }
        time.sleep(0.1)  # FRED rate limit courtesy

    return results


def print_yield_curve():
    """Print Treasury yield curve data."""
    data = fetch_yield_curve()
    if not data:
        print("Failed to fetch yield curve data")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*70}")
    print(f"TREASURY YIELD CURVE — {now}")
    print(f"Source: FRED (free API key)")
    print(f"{'='*70}")

    # Yields
    print(f"\n{'Instrument':<25} {'Yield':>8} {'As Of':>12}")
    print("-" * 50)
    for sid in ["DFF", "DGS3M", "DGS2", "DGS10", "DGS30"]:
        if sid in data:
            d = data[sid]
            print(f"{d['name']:<25} {d['value']:>7.2f}% {d['date']:>12}")

    # Spreads
    print(f"\n{'Spread':<25} {'Value':>8} {'Signal':>15}")
    print("-" * 55)
    if "T10Y2Y" in data:
        spread = data["T10Y2Y"]["value"]
        signal = "INVERTED ⚠️" if spread < 0 else "Steepening" if spread > 0.5 else "Normal"
        print(f"{data['T10Y2Y']['name']:<25} {spread:>+7.2f}% {signal:>15}")
    if "T10Y3M" in data:
        spread = data["T10Y3M"]["value"]
        signal = "INVERTED ⚠️" if spread < 0 else "Steepening" if spread > 0.5 else "Normal"
        print(f"{data['T10Y3M']['name']:<25} {spread:>+7.2f}% {signal:>15}")

    # Fed funds vs 10Y
    if "DFF" in data and "DGS10" in data:
        real_spread = data["DGS10"]["value"] - data["DFF"]["value"]
        print(f"{'10Y - Fed Funds':<25} {real_spread:>+7.2f}% {'':>15}")

    # Interpretation
    if "T10Y2Y" in data:
        s = data["T10Y2Y"]["value"]
        if s < 0:
            print(f"\n🔴 YIELD CURVE INVERTED — Recession risk elevated (10Y < 2Y)")
        elif s < 0.25:
            print(f"\n🟡 YIELD CURVE FLAT — Economy slowing, watch for inversion")
        else:
            print(f"\n🟢 YIELD CURVE NORMAL/STEEP — Growth environment")


# ─── CFTC COT REPORTS (OFR API) ───

COT_API = "https://data.financialresearch.gov/hf/v1/series/dataset?dataset=tff&output=json"

# Series we care about for trading
COT_SERIES = {
    "TFF-LF_BITCOIN_NET_POSITION": "Bitcoin (CME)",
    "TFF-LF_SP_LONG_POSITION": "S&P 500 Long",
    "TFF-LF_SP_SHORT_POSITION": "S&P 500 Short",
    "TFF-LF_SP_NET_POSITION": "S&P 500 Net",
}


def fetch_cot_data():
    """Fetch CFTC Commitments of Traders data from OFR API."""
    data = get_json_with_decompress(COT_API)
    if isinstance(data, dict) and "error" in data:
        return None
    if not isinstance(data, dict) or "timeseries" not in data:
        return None

    ts = data["timeseries"]
    results = {}

    for series_id, name in COT_SERIES.items():
        if series_id in ts:
            series = ts[series_id]
            agg = series.get("timeseries", {}).get("aggregation", [])
            if agg and isinstance(agg, list):
                # Get last 5 data points [date, value]
                recent = agg[-5:]
                results[series_id] = {
                    "name": name,
                    "data": [{"date": d[0], "value": d[1]} for d in recent],
                }

    return results


def get_json_with_decompress(url):
    """GET from API with decompression support."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--compressed", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35
        )
        return json.loads(result.stdout) if result.stdout else {}
    except Exception as e:
        return {"error": str(e)}


def print_cot():
    """Print CFTC COT report data."""
    data = fetch_cot_data()
    if not data:
        print("Failed to fetch COT data")
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*70}")
    print(f"CFTC COMMITMENTS OF TRADERS (COT) — {now}")
    print(f"Source: OFR Financial Research (FREE, no key)")
    print(f"{'='*70}")

    for series_id, info in data.items():
        print(f"\n{info['name']}:")
        for point in reversed(info["data"]):
            val = point["value"]
            if abs(val) >= 1e9:
                val_str = f"${val/1e9:.2f}B"
            elif abs(val) >= 1e6:
                val_str = f"${val/1e6:.1f}M"
            else:
                val_str = f"{val:,.0f}"
            print(f"  {point['date']}  {val_str}")

    # BTC interpretation
    btc = data.get("TFF-LF_BITCOIN_NET_POSITION", {})
    if btc and btc["data"]:
        latest = btc["data"][-1]["value"]
        prev = btc["data"][-2]["value"] if len(btc["data"]) > 1 else 0
        change = latest - prev
        if latest < 0:
            print(f"\n📊 BTC Net Position: SHORT ${abs(latest)/1e9:.2f}B")
            if change < 0:
                print(f"   Shorts INCREASING (${abs(change)/1e6:.0f}M more short vs last week)")
            else:
                print(f"   Shorts DECREASING (${abs(change)/1e6:.0f}M less short vs last week)")
        else:
            print(f"\n📊 BTC Net Position: LONG ${latest/1e9:.2f}B")
            if change > 0:
                print(f"   Longs INCREASING (${change/1e6:.0f}M more long vs last week)")
            else:
                print(f"   Longs DECREASING (${abs(change)/1e6:.0f}M less long vs last week)")


# ─── MAIN ───

def main():
    parser = argparse.ArgumentParser(description="Macro Liquidity & Sentiment Data Fetcher")
    parser.add_argument("--hl", action="store_true", help="Hyperliquid funding + OI")
    parser.add_argument("--fng", action="store_true", help="Crypto Fear & Greed Index")
    parser.add_argument("--stable", action="store_true", help="Stablecoin flows")
    parser.add_argument("--yield", action="store_true", help="Treasury yield curve")
    parser.add_argument("--cot", action="store_true", help="CFTC COT reports")
    parser.add_argument("--hl-symbols", nargs="+", metavar="SYM", help="Specific HL perp symbols")
    args = parser.parse_args()

    # If no args, run everything
    has_yield = getattr(args, "yield", False)
    run_all = not any([args.hl, args.fng, args.stable, has_yield, args.cot, args.hl_symbols])

    if args.hl or run_all:
        print_hl_funding()
    if args.fng or run_all:
        print_fng()
    if args.stable or run_all:
        print_stablecoins()
    if has_yield or run_all:
        print_yield_curve()
    if args.cot or run_all:
        print_cot()
    if args.hl_symbols:
        print_hl_funding(args.hl_symbols)


if __name__ == "__main__":
    main()
