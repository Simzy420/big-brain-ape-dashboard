#!/usr/bin/env python3
"""
Financial Modeling Prep (FMP) Data Fetcher — Starter Tier
API Key: FYPPeClubVq4A3KcyNkDH5S1g2Rw1SCL

WORKING ENDPOINTS (200):
  - profile          : Company info, sector, industry, beta, description
  - quote            : Real-time price, volume, 50/200d MA, market cap, day/year range
  - quote-short      : Compact price + change (single symbol only — batch is 402)
  - income-statement : Quarterly/annual revenue, gross profit, EPS, EBITDA, net income
  - balance-sheet    : Full assets, liabilities, equity (5 periods)
  - cash-flow        : Operating, investing, financing flows (5 periods)
  - discounted-cash-flow : Intrinsic/fair value vs current price
  - historical-price-eod : Full daily price history (1000+ bars)
  - commodities      : GCUSD (Gold), BZUSD (Brent), SIUSD (Silver), etc.
  - crypto           : BTCUSD, ETHUSD, SOLUSD, etc.

LOCKED ENDPOINTS (402 — Premium):
  key-metrics, ratios, analyst-estimates, transcripts, technical-indicators,
  batch quotes, economic-calendar, forex, stock-screener, sector-performance

Usage:
  python3 fmp-data-fetch.py --quote NVDA
  python3 fmp-data-fetch.py --profile NVDA
  python3 fmp-data-fetch.py --financials NVDA          # income + balance + cashflow
  python3 fmp-data-fetch.py --dcf NVDA
  python3 fmp-data-fetch.py --history NVDA             # daily price history
  python3 fmp-data-fetch.py --history NVDA --limit 60  # last 60 days
  python3 fmp-data-fetch.py --commodities
  python3 fmp-data-fetch.py --crypto
  python3 fmp-data-fetch.py --full NVDA                # everything: profile + quote + financials + DCF
  python3 fmp-data-fetch.py --batch NVDA AAPL MSFT     # sequential single-symbol quotes
  python3 fmp-data-fetch.py --rsi NVDA                 # computed RSI(14) from history
  python3 fmp-data-fetch.py --sma NVDA                 # computed SMA(20,50,200) from history
  python3 fmp-data-fetch.py --levels NVDA              # support/resistance from history
  python3 fmp-data-fetch.py --analysis NVDA            # full technical + fundamental analysis
"""

import json
import sys
import time
import argparse
import subprocess
from datetime import datetime, timezone

FMP_KEY = "FYPPeClubVq4A3KcyNkDH5S1g2Rw1SCL"
BASE_URL = "https://financialmodelingprep.com/stable"

# Stocks tradeable as xyz: perps on Hyperliquid (trade.xyz)
STOCK_PERPS = [
    "NVDA", "META", "GOOGL", "AAPL", "MSFT", "AMZN", "AMD", "INTC",
    "PLTR", "NFLX", "ORCL", "TSM", "COIN", "HOOD", "MSTR", "TSLA",
    "RIVN", "BABA", "GME", "COST", "LLY", "HIMS", "DKNG", "MU", "SNDK",
    "SKHX", "KIOXIA", "CRCL", "CRWV", "SOFTBANK", "HYUNDAI",
]

# Commodity symbols on FMP
COMMODITIES = {
    "GCUSD": "Gold",
    "SIUSD": "Silver",
    "BZUSD": "Brent Oil",
    "CLUSD": "WTI Crude",
    "NGUSD": "Natural Gas",
    "HGUSD": "Copper",
    "PLUSD": "Platinum",
    "PAUSD": "Palladium",
}

# Crypto symbols on FMP
CRYPTO = {
    "BTCUSD": "Bitcoin",
    "ETHUSD": "Ethereum",
    "SOLUSD": "Solana",
    "XRPUSD": "Ripple",
    "DOGEUSD": "Dogecoin",
    "LINKUSD": "Chainlink",
    "AVAXUSD": "Avalanche",
    "BNBUSD": "BNB",
    "LTCUSD": "Litecoin",
    "XMRUSD": "Monero",
    "ZECUSD": "Zcash",
}


def fmp_get(endpoint, params=None):
    """Make an FMP stable API call via curl."""
    params = params or {}
    params["apikey"] = FMP_KEY
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE_URL}/{endpoint}?{query}"
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        data = json.loads(result.stdout) if result.stdout else {}
        if isinstance(data, dict) and "Error Message" in data:
            return {"error": data["Error Message"]}
        return data
    except Exception as e:
        return {"error": str(e)}


def fetch_quote(symbol):
    """Full real-time quote with 50/200d MAs, market cap, ranges."""
    data = fmp_get("quote", {"symbol": symbol})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list) or not data:
        return None
    q = data[0]
    return {
        "symbol": q.get("symbol", symbol),
        "name": q.get("name", ""),
        "price": q.get("price", 0),
        "change": q.get("change", 0),
        "change_pct": q.get("changePercentage", 0),
        "volume": q.get("volume", 0),
        "day_low": q.get("dayLow", 0),
        "day_high": q.get("dayHigh", 0),
        "year_low": q.get("yearLow", 0),
        "year_high": q.get("yearHigh", 0),
        "market_cap": q.get("marketCap", 0),
        "sma_50": q.get("priceAvg50", 0),
        "sma_200": q.get("priceAvg200", 0),
        "exchange": q.get("exchange", ""),
        "open": q.get("open", 0),
        "prev_close": q.get("previousClose", 0),
    }


def fetch_quote_short(symbol):
    """Compact quote — price, change, volume only."""
    data = fmp_get("quote-short", {"symbol": symbol})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list) or not data:
        return None
    q = data[0]
    return {
        "symbol": q.get("symbol", symbol),
        "price": q.get("price", 0),
        "change": q.get("change", 0),
        "volume": q.get("volume", 0),
    }


def fetch_profile(symbol):
    """Company profile — sector, industry, description, beta, CEO, etc."""
    data = fmp_get("profile", {"symbol": symbol})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list) or not data:
        return None
    p = data[0]
    return {
        "symbol": p.get("symbol", symbol),
        "name": p.get("companyName", ""),
        "price": p.get("price", 0),
        "market_cap": p.get("marketCap", 0),
        "beta": p.get("beta", 0),
        "last_dividend": p.get("lastDividend", 0),
        "range": p.get("range", ""),
        "change": p.get("change", 0),
        "change_pct": p.get("changePercentage", 0),
        "volume": p.get("volume", 0),
        "avg_volume": p.get("averageVolume", 0),
        "exchange": p.get("exchange", ""),
        "industry": p.get("industry", ""),
        "website": p.get("website", ""),
        "description": p.get("description", ""),
        "ceo": p.get("ceo", ""),
        "sector": p.get("sector", ""),
        "country": p.get("country", ""),
        "employees": p.get("fullTimeEmployees", ""),
        "ipo_date": p.get("ipoDate", ""),
        "is_etf": p.get("isEtf", False),
        "is_active": p.get("isActivelyTrading", False),
        "is_adr": p.get("isAdr", False),
    }


def fetch_income_statement(symbol, period="quarter"):
    """Quarterly or annual income statement."""
    data = fmp_get("income-statement", {"symbol": symbol, "period": period})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list):
        return None
    return data


def fetch_balance_sheet(symbol, period="quarter"):
    """Quarterly or annual balance sheet."""
    data = fmp_get("balance-sheet-statement", {"symbol": symbol, "period": period})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list):
        return None
    return data


def fetch_cash_flow(symbol, period="quarter"):
    """Quarterly or annual cash flow statement."""
    data = fmp_get("cash-flow-statement", {"symbol": symbol, "period": period})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list):
        return None
    return data


def fetch_dcf(symbol):
    """Discounted Cash Flow — intrinsic/fair value vs current price."""
    data = fmp_get("discounted-cash-flow", {"symbol": symbol})
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list) or not data:
        return None
    d = data[0]
    return {
        "symbol": d.get("symbol", symbol),
        "date": d.get("date", ""),
        "dcf_value": d.get("dcf", 0),
        "stock_price": d.get("Stock Price", 0),
        "upside_pct": ((d.get("dcf", 0) - d.get("Stock Price", 0)) / d.get("Stock Price", 1) * 100) if d.get("Stock Price") else 0,
    }


def fetch_historical_prices(symbol, limit=0):
    """Full daily EOD price history. Returns list of {date, close, volume}.
    FMP 'light' endpoint uses 'price' field — normalized to 'close' here."""
    params = {"symbol": symbol}
    data = fmp_get("historical-price-eod/light", params)
    if isinstance(data, dict) and "error" in data:
        return None
    if not data or not isinstance(data, list):
        return None
    # Normalize 'price' -> 'close'
    for bar in data:
        if "close" not in bar and "price" in bar:
            bar["close"] = bar["price"]
    if limit > 0:
        return data[:limit]
    return data


# ─── COMPUTED TECHNICAL INDICATORS (from historical price data) ───

def compute_rsi(prices, period=14):
    """Compute RSI from a list of closing prices (most recent first)."""
    if len(prices) < period + 1:
        return None
    # Reverse to oldest-first
    closes = list(reversed(prices[:period + 1]))
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def compute_sma(prices, period):
    """Simple Moving Average from list of closes (most recent first)."""
    if len(prices) < period:
        return None
    return round(sum(prices[:period]) / period, 2)


def compute_ema(prices, period):
    """Exponential Moving Average from list of closes (most recent first)."""
    if len(prices) < period:
        return None
    closes = list(reversed(prices[:period * 3]))  # need more data for EMA warmup
    multiplier = 2 / (period + 1)
    ema = sum(closes[:period]) / period  # seed with SMA
    for close in closes[period:]:
        ema = (close - ema) * multiplier + ema
    return round(ema, 2)


def compute_support_resistance(prices, lookback=90):
    """Identify support and resistance levels from recent price history."""
    if len(prices) < 10:
        return {"support": [], "resistance": []}
    chunk = prices[:lookback] if len(prices) >= lookback else prices
    closes = [p for p in chunk]
    current = closes[0]

    # Simple pivot detection: local minima/maxima
    supports = []
    resistances = []
    window = 5
    for i in range(window, len(chunk) - window):
        left = chunk[i-window:i]
        right = chunk[i+1:i+window+1]
        if chunk[i] == min(left + [chunk[i]] + right):
            supports.append(chunk[i])
        if chunk[i] == max(left + [chunk[i]] + right):
            resistances.append(chunk[i])

    # Deduplicate and sort, keep those near current price
    supports = sorted(set([round(s, 2) for s in supports if s < current]), reverse=True)[:3]
    resistances = sorted(set([round(r, 2) for r in resistances if r > current]))[:3]

    return {
        "current": round(current, 2),
        "support": supports,
        "resistance": resistances,
    }


# ─── FORMATTING / DISPLAY ───

def fmt_volume(v):
    """Format volume/market cap human-readable."""
    if not v:
        return "N/A"
    if v >= 1e12:
        return f"${v/1e12:.2f}T"
    elif v >= 1e9:
        return f"${v/1e9:.2f}B"
    elif v >= 1e6:
        return f"${v/1e6:.2f}M"
    elif v >= 1e3:
        return f"${v/1e3:.2f}K"
    return f"${v:.2f}"


def print_quote(q):
    print(f"Symbol:     {q['symbol']}")
    print(f"Name:       {q['name']}")
    print(f"Price:      ${q['price']:.2f}")
    print(f"Change:     ${q['change']:+.2f} ({q['change_pct']:+.2f}%)")
    print(f"Volume:     {fmt_volume(q['volume'])}")
    print(f"Day Range:  ${q['day_low']:.2f} - ${q['day_high']:.2f}")
    print(f"Year Range: ${q['year_low']:.2f} - ${q['year_high']:.2f}")
    print(f"Market Cap: {fmt_volume(q['market_cap'])}")
    print(f"SMA-50:     ${q['sma_50']:.2f}")
    print(f"SMA-200:    ${q['sma_200']:.2f}")
    print(f"Exchange:   {q['exchange']}")
    if q['sma_50'] and q['sma_200']:
        if q['price'] > q['sma_50'] > q['sma_200']:
            print("Trend:      BULLISH (price > SMA50 > SMA200)")
        elif q['price'] < q['sma_50'] < q['sma_200']:
            print("Trend:      BEARISH (price < SMA50 < SMA200)")
        else:
            print("Trend:      MIXED")


def print_profile(p):
    print(f"Symbol:     {p['symbol']}")
    print(f"Name:       {p['name']}")
    print(f"Sector:     {p['sector']}")
    print(f"Industry:   {p['industry']}")
    print(f"CEO:        {p['ceo']}")
    print(f"Beta:       {p['beta']}")
    print(f"Market Cap: {fmt_volume(p['market_cap'])}")
    print(f"52w Range:  {p['range']}")
    print(f"Employees:  {p['employees']}")
    print(f"IPO Date:   {p['ipo_date']}")
    print(f"Exchange:   {p['exchange']}")
    print(f"Website:    {p['website']}")
    print(f"Active:     {p['is_active']}")
    print(f"\nDescription:")
    print(f"  {p['description'][:500]}{'...' if len(p['description']) > 500 else ''}")


def print_financials(symbol):
    print(f"\n{'='*80}")
    print(f"INCOME STATEMENT — {symbol} (Quarterly)")
    print(f"{'='*80}")
    inc = fetch_income_statement(symbol)
    if inc:
        for q in inc[:4]:  # Last 4 quarters
            rev = q.get("revenue", 0)
            ni = q.get("netIncome", 0)
            eps = q.get("eps", 0)
            gp = q.get("grossProfit", 0)
            gm = (gp / rev * 100) if rev else 0
            nm = (ni / rev * 100) if rev else 0
            print(f"  {q.get('date','?')}: Rev={fmt_volume(rev)}, GP={fmt_volume(gp)} (GM={gm:.1f}%), NI={fmt_volume(ni)} (NM={nm:.1f}%), EPS=${eps:.2f}")
    else:
        print("  N/A")

    print(f"\n{'='*80}")
    print(f"BALANCE SHEET — {symbol} (Quarterly)")
    print(f"{'='*80}")
    bs = fetch_balance_sheet(symbol)
    if bs:
        for q in bs[:4]:
            assets = q.get("totalAssets", 0)
            liab = q.get("totalLiabilities", 0)
            equity = q.get("totalStockholdersEquity", 0)
            cash = q.get("cashAndCashEquivalents", 0)
            debt = q.get("totalDebt", 0)
            print(f"  {q.get('date','?')}: Assets={fmt_volume(assets)}, Liab={fmt_volume(liab)}, Equity={fmt_volume(equity)}, Cash={fmt_volume(cash)}, Debt={fmt_volume(debt)}")
    else:
        print("  N/A")

    print(f"\n{'='*80}")
    print(f"CASH FLOW — {symbol} (Quarterly)")
    print(f"{'='*80}")
    cf = fetch_cash_flow(symbol)
    if cf:
        for q in cf[:4]:
            op = q.get("operatingCashFlow", 0)
            inv = q.get("netCashUsedForInvestingActivites", 0)
            fin = q.get("netCashUsedProvidedByFinancingActivities", 0)
            fcf = q.get("freeCashFlow", 0)
            print(f"  {q.get('date','?')}: OCF={fmt_volume(op)}, Inv={fmt_volume(inv)}, Fin={fmt_volume(fin)}, FCF={fmt_volume(fcf)}")
    else:
        print("  N/A")


def print_dcf(d):
    print(f"Symbol:       {d['symbol']}")
    print(f"Date:         {d['date']}")
    print(f"DCF Value:    ${d['dcf_value']:.2f}")
    print(f"Stock Price:  ${d['stock_price']:.2f}")
    print(f"Upside:       {d['upside_pct']:+.1f}%")
    if d['upside_pct'] > 15:
        print("Verdict:      UNDERVALUED (DCF >15% above market)")
    elif d['upside_pct'] < -15:
        print("Verdict:      OVERVALUED (DCF >15% below market)")
    else:
        print("Verdict:      FAIRLY VALUED (within ±15% of market)")


def print_history(h, limit=10):
    print(f"{'Date':<12} {'Close':>10} {'Volume':>15}")
    print("-" * 40)
    for bar in h[:limit]:
        print(f"{bar.get('date','?'):<12} ${bar.get('close',0):>9.2f} {fmt_volume(bar.get('volume',0)):>15}")


def print_technicals(symbol):
    """Full technical analysis computed from historical data."""
    print(f"\n{'='*80}")
    print(f"TECHNICAL ANALYSIS — {symbol}")
    print(f"{'='*80}")
    hist = fetch_historical_prices(symbol)
    if not hist or len(hist) < 20:
        print("Insufficient historical data")
        return

    closes = [bar.get("close", 0) for bar in hist]

    # SMAs
    sma_20 = compute_sma(closes, 20)
    sma_50 = compute_sma(closes, 50) if len(closes) >= 50 else None
    sma_200 = compute_sma(closes, 200) if len(closes) >= 200 else None

    print(f"Current Price: ${closes[0]:.2f}")
    print(f"SMA-20:        ${sma_20:.2f}" if sma_20 else "SMA-20:        N/A")
    print(f"SMA-50:        ${sma_50:.2f}" if sma_50 else "SMA-50:        N/A")
    print(f"SMA-200:       ${sma_200:.2f}" if sma_200 else "SMA-200:       N/A")

    # RSI
    rsi = compute_rsi(closes, 14)
    if rsi is not None:
        print(f"RSI(14):       {rsi:.1f}", end="")
        if rsi > 70:
            print(" — OVERBOUGHT")
        elif rsi < 30:
            print(" — OVERSOLD")
        else:
            print(" — Neutral")
    else:
        print("RSI(14):       N/A")

    # Support/Resistance
    sr = compute_support_resistance(closes, 90)
    print(f"\nSupport/Resistance (90-day lookback):")
    print(f"  Current:      ${sr['current']:.2f}")
    print(f"  Resistance:   {', '.join(f'${r}' for r in sr['resistance']) if sr['resistance'] else 'None identified'}")
    print(f"  Support:      {', '.join(f'${s}' for s in sr['support']) if sr['support'] else 'None identified'}")

    # 52-week range
    year_high = max(closes[:252]) if len(closes) >= 252 else max(closes)
    year_low = min(closes[:252]) if len(closes) >= 252 else min(closes)
    current = closes[0]
    pct_from_high = (current - year_high) / year_high * 100
    pct_from_low = (current - year_low) / year_low * 100
    print(f"\n52-Week Range:")
    print(f"  High:         ${year_high:.2f} ({pct_from_high:+.1f}% from current)")
    print(f"  Low:          ${year_low:.2f} ({pct_from_low:+.1f}% from current)")
    print(f"  Position:     {(current - year_low)/(year_high - year_low)*100:.0f}% of range")


def print_full_analysis(symbol):
    """Complete fundamental + technical analysis for a stock."""
    print(f"\n{'#'*80}")
    print(f"# FULL ANALYSIS — {symbol}")
    print(f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'#'*80}")

    # Profile
    print(f"\n{'='*80}")
    print("COMPANY PROFILE")
    print(f"{'='*80}")
    p = fetch_profile(symbol)
    if p:
        print_profile(p)
    else:
        print("Profile: N/A")

    # Quote
    print(f"\n{'='*80}")
    print("REAL-TIME QUOTE")
    print(f"{'='*80}")
    q = fetch_quote(symbol)
    if q:
        print_quote(q)
    else:
        print("Quote: N/A")

    # Financials
    print_financials(symbol)

    # DCF
    print(f"\n{'='*80}")
    print("DISCOUNTED CASH FLOW VALUATION")
    print(f"{'='*80}")
    d = fetch_dcf(symbol)
    if d:
        print_dcf(d)
    else:
        print("DCF: N/A")

    # Technicals
    print_technicals(symbol)

    # Summary verdict
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    points = []
    if q:
        if q['price'] > q['sma_50'] > q.get('sma_200', 0) and q['sma_200']:
            points.append("Bullish trend structure (price > SMA50 > SMA200)")
        elif q['price'] < q['sma_50'] and q['sma_200'] and q['price'] < q['sma_200']:
            points.append("Bearish trend structure (price < SMA50 < SMA200)")
    if d:
        if d['upside_pct'] > 15:
            points.append(f"Undervalued by DCF ({d['upside_pct']:+.1f}% upside to fair value)")
        elif d['upside_pct'] < -15:
            points.append(f"Overvalued by DCF ({d['upside_pct']:+.1f}% vs fair value)")
    closes = None
    hist = fetch_historical_prices(symbol)
    if hist and len(hist) >= 15:
        closes = [bar.get("close", 0) for bar in hist]
        rsi = compute_rsi(closes, 14)
        if rsi:
            if rsi > 70:
                points.append(f"RSI overbought ({rsi:.0f}) — pullback risk")
            elif rsi < 30:
                points.append(f"RSI oversold ({rsi:.0f}) — bounce setup")
    for pt in points:
        print(f"  • {pt}")
    if not points:
        print("  • No strong signals — mixed/neutral")


def print_commodities():
    print(f"\n{'='*80}")
    print(f"COMMODITY PRICES — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Source: FMP (Starter tier)")
    print(f"{'='*80}")
    print(f"{'Symbol':<10} {'Name':<15} {'Price':>10} {'Change':>10} {'Volume':>10}")
    print("-" * 60)
    for sym, name in COMMODITIES.items():
        q = fetch_quote_short(sym)
        if q:
            print(f"{sym:<10} {name:<15} ${q['price']:>9.2f} {q['change']:>+9.2f} {fmt_volume(q['volume']):>10}")
        else:
            print(f"{sym:<10} {name:<15} {'N/A':>10}")
        time.sleep(0.1)


def print_crypto():
    print(f"\n{'='*80}")
    print(f"CRYPTO PRICES — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Source: FMP (Starter tier)")
    print(f"{'='*80}")
    print(f"{'Symbol':<10} {'Name':<15} {'Price':>12} {'Change':>10} {'Volume':>15}")
    print("-" * 65)
    for sym, name in CRYPTO.items():
        q = fetch_quote_short(sym)
        if q:
            print(f"{sym:<10} {name:<15} ${q['price']:>11.2f} {q['change']:>+9.2f} {fmt_volume(q['volume']):>15}")
        else:
            print(f"{sym:<10} {name:<15} {'N/A':>12}")
        time.sleep(0.1)


def print_batch_quotes(symbols):
    """Sequential single-symbol quotes (batch endpoint is locked)."""
    print(f"\n{'='*80}")
    print(f"BATCH QUOTES — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*80}")
    print(f"{'Symbol':<10} {'Price':>10} {'Change%':>10} {'Volume':>12} {'MarketCap':>12}")
    print("-" * 60)
    for sym in symbols:
        q = fetch_quote(sym)
        if q:
            print(f"{sym:<10} ${q['price']:>9.2f} {q['change_pct']:>+9.2f}% {fmt_volume(q['volume']):>12} {fmt_volume(q['market_cap']):>12}")
        else:
            print(f"{sym:<10} {'N/A':>10}")
        time.sleep(0.1)


# ─── MAIN ───

def main():
    parser = argparse.ArgumentParser(description="FMP Data Fetcher")
    parser.add_argument("--quote", metavar="SYM", help="Real-time quote")
    parser.add_argument("--profile", metavar="SYM", help="Company profile")
    parser.add_argument("--financials", metavar="SYM", help="Income + Balance + Cash Flow")
    parser.add_argument("--dcf", metavar="SYM", help="DCF valuation")
    parser.add_argument("--history", metavar="SYM", help="Historical daily prices")
    parser.add_argument("--commodities", action="store_true", help="Commodity prices")
    parser.add_argument("--crypto", action="store_true", help="Crypto prices")
    parser.add_argument("--batch", nargs="+", metavar="SYM", help="Multiple quotes (sequential)")
    parser.add_argument("--rsi", metavar="SYM", help="Computed RSI(14)")
    parser.add_argument("--sma", metavar="SYM", help="Computed SMAs (20/50/200)")
    parser.add_argument("--levels", metavar="SYM", help="Support/resistance levels")
    parser.add_argument("--analysis", metavar="SYM", help="Full technical + fundamental analysis")
    parser.add_argument("--full", metavar="SYM", help="Everything: profile + quote + financials + DCF + technicals")
    parser.add_argument("--limit", type=int, default=10, help="Limit for --history (default 10)")
    args = parser.parse_args()

    if args.quote:
        q = fetch_quote(args.quote)
        if q:
            print_quote(q)
        else:
            print(f"No quote for {args.quote}")

    elif args.profile:
        p = fetch_profile(args.profile)
        if p:
            print_profile(p)
        else:
            print(f"No profile for {args.profile}")

    elif args.financials:
        print_financials(args.financials)

    elif args.dcf:
        d = fetch_dcf(args.dcf)
        if d:
            print_dcf(d)
        else:
            print(f"No DCF for {args.dcf}")

    elif args.history:
        h = fetch_historical_prices(args.history)
        if h:
            print_history(h, args.limit)
        else:
            print(f"No history for {args.history}")

    elif args.commodities:
        print_commodities()

    elif args.crypto:
        print_crypto()

    elif args.batch:
        print_batch_quotes(args.batch)

    elif args.rsi:
        hist = fetch_historical_prices(args.rsi)
        if hist and len(hist) >= 15:
            closes = [bar.get("close", 0) for bar in hist]
            rsi = compute_rsi(closes, 14)
            if rsi is not None:
                print(f"RSI(14) for {args.rsi}: {rsi:.1f}", end="")
                if rsi > 70:
                    print(" — OVERBOUGHT")
                elif rsi < 30:
                    print(" — OVERSOLD")
                else:
                    print(" — Neutral")
            else:
                print("Insufficient data for RSI")
        else:
            print(f"No historical data for {args.rsi}")

    elif args.sma:
        hist = fetch_historical_prices(args.sma)
        if hist:
            closes = [bar.get("close", 0) for bar in hist]
            sma_20 = compute_sma(closes, 20)
            sma_50 = compute_sma(closes, 50) if len(closes) >= 50 else None
            sma_200 = compute_sma(closes, 200) if len(closes) >= 200 else None
            print(f"Current:  ${closes[0]:.2f}")
            print(f"SMA-20:  ${sma_20:.2f}" if sma_20 else "SMA-20:  N/A")
            print(f"SMA-50:  ${sma_50:.2f}" if sma_50 else "SMA-50:  N/A")
            print(f"SMA-200: ${sma_200:.2f}" if sma_200 else "SMA-200: N/A")

    elif args.levels:
        hist = fetch_historical_prices(args.levels)
        if hist:
            closes = [bar.get("close", 0) for bar in hist]
            sr = compute_support_resistance(closes, 90)
            print(f"Current:      ${sr['current']:.2f}")
            print(f"Resistance:   {', '.join(f'${r}' for r in sr['resistance']) if sr['resistance'] else 'None identified'}")
            print(f"Support:      {', '.join(f'${s}' for s in sr['support']) if sr['support'] else 'None identified'}")

    elif args.analysis or args.full:
        sym = args.analysis or args.full
        print_full_analysis(sym)


if __name__ == "__main__":
    main()
