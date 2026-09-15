#!/usr/bin/env python3.11
"""
Ticker Cache Pre-Generator
Pre-builds ticker analyses for instant delivery when users type /TICKER.
Runs as a script-only cron (no LLM needed) every 4 hours.

Output: ~/.hermes/cron/ticker-cache/{TICKER}.md
"""

import json
import os
import subprocess
import sys
import requests
from datetime import datetime, timezone

# Top 20 most likely requested tickers
TICKERS = [
    # Crypto (most popular for this bot's audience)
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    # Mega-cap tech
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN",
    "META", "GOOGL", "AMD",
    # Hot/meme
    "COIN", "HOOD", "MSTR", "PLTR",
    # Commodity tickers (silver needs paid plan on Twelve Data, skip for now)
    "GOLD",
    # Indices
    "SP500",
]

CACHE_DIR = "/home/hermes/.hermes/cron/ticker-cache"
os.makedirs(CACHE_DIR, exist_ok=True)

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "d9dpmp9r01qujggob290d9dpmp9r01qujggob29g")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "eeb30f15647e4a68af4c457965ff045f")
FMP_KEY = os.environ.get("FMP_API_KEY", "FYPPeClubVq4A3KcyNkDH5S1g2Rw1SCL")
FMP_BASE = "https://financialmodelingprep.com/stable"
AV_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "MZZ7TATAR2PBIZW0")
AV_BASE = "https://www.alphavantage.co/query"

# CoinGecko coin ID mapping (free API, no key needed, ~30 calls/min)
COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
    "DOGE": "dogecoin",
}

def fetch_coingecko_quote(symbols):
    """Fetch quotes for multiple crypto tickers from CoinGecko (FREE, no key, batch call)"""
    ids = []
    for s in symbols:
        if s in COINGECKO_IDS:
            ids.append(COINGECKO_IDS[s])
    if not ids:
        return {}
    id_str = ",".join(ids)
    try:
        result = subprocess.run(
            ["curl", "-s", f"https://api.coingecko.com/api/v3/simple/price?ids={id_str}&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true&include_last_updated_at=true"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        quotes = {}
        for symbol, cg_id in COINGECKO_IDS.items():
            if cg_id in data:
                d = data[cg_id]
                quotes[symbol] = {
                    "price": d.get("usd", 0),
                    "change_pct": d.get("usd_24h_change", 0),
                    "change": d.get("usd", 0) * d.get("usd_24h_change", 0) / 100,
                    "volume_24h": d.get("usd_24h_vol", 0),
                    "last_updated": d.get("last_updated_at"),
                }
        return quotes
    except Exception as e:
        #SILENT_print_(f"  CoinGecko error: {e}", file=sys.stderr)
        return {}

def fetch_coingecko_ohlc(symbol, days=30):
    """Fetch daily OHLC bars from CoinGecko (FREE, no key)"""
    cg_id = COINGECKO_IDS.get(symbol)
    if not cg_id:
        return None
    try:
        result = subprocess.run(
            ["curl", "-s", f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc?vs_currency=usd&days={days}"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        if isinstance(data, list) and len(data) > 0:
            bars = []
            for bar in data:  # [timestamp, open, high, low, close]
                bars.append({
                    "date": datetime.fromtimestamp(bar[0]/1000, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "open": bar[1],
                    "high": bar[2],
                    "low": bar[3],
                    "close": bar[4],
                    "volume": None,
                })
            bars.reverse()  # Most recent first to match existing format
            return bars
    except Exception as e:
        #SILENT_print_(f"  CoinGecko OHLC error for {symbol}: {e}", file=sys.stderr)
    return None

def fetch_finnhub_analyst_ratings(symbol):
    """Fetch analyst recommendations from Finnhub (free with email verification)"""
    try:
        result = subprocess.run(
            ["curl", "-s", f"https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={FINNHUB_KEY}"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        if isinstance(data, list) and len(data) > 0:
            latest = data[0]
            buys = latest.get("buy", 0)
            holds = latest.get("hold", 0)
            sells = latest.get("sell", 0)
            strong_buys = latest.get("strongBuy", 0)
            strong_sells = latest.get("strongSell", 0)
            total = buys + holds + sells + strong_buys + strong_sells
            if total > 0:
                bull_pct = ((strong_buys + buys) / total) * 100
                return {
                    "strong_buy": strong_buys,
                    "buy": buys,
                    "hold": holds,
                    "sell": sells,
                    "strong_sell": strong_sells,
                    "total": total,
                    "bull_pct": bull_pct,
                    "consensus": "STRONG BUY" if bull_pct >= 75 else "BUY" if bull_pct >= 60 else "HOLD" if bull_pct >= 40 else "SELL"
                }
    except Exception as e:
        #SILENT_print_(f"  Analyst ratings error for {symbol}: {e}", file=sys.stderr)
    return None

def fetch_finnhub_earnings(symbol):
    """Fetch upcoming earnings date from Finnhub (free with email verification)"""
    try:
        from datetime import datetime as dt, timedelta
        today = dt.now().strftime("%Y-%m-%d")
        end_date = (dt.now() + timedelta(days=180)).strftime("%Y-%m-%d")
        result = subprocess.run(
            ["curl", "-s", f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={end_date}&token={FINNHUB_KEY}"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        events = data.get("earningsCalendar", [])
        # Filter for this specific symbol
        upcoming = [e for e in events if e.get("symbol") == symbol and e.get("date", "") >= today]
        if upcoming:
            next_earn = upcoming[0]
            return {
                "date": next_earn.get("date"),
                "eps_estimate": next_earn.get("epsEstimate"),
                "revenue_estimate": next_earn.get("revenueEstimate"),
            }
    except Exception as e:
        #SILENT_print_(f"  Earnings error for {symbol}: {e}", file=sys.stderr)
    return None

def fetch_finnhub_quote(symbol):
    """Fetch real-time quote from Finnhub (FREE)"""
    # Map our tickers to Finnhub symbols
    symbol_map = {
        "BTC": "BTC", "ETH": "ETH", "SOL": "SOL", "XRP": "XRP", "DOGE": "DOGE",
        "NVDA": "NVDA", "TSLA": "TSLA", "AAPL": "AAPL", "MSFT": "MSFT", "AMZN": "AMZN",
        "META": "META", "GOOGL": "GOOGL", "AMD": "AMD",
        "COIN": "COIN", "HOOD": "HOOD", "MSTR": "MSTR", "PLTR": "PLTR",
        "GOLD": "OANDA:XAU_USD", "SILVER": "OANDA:XAG_USD",
        "SP500": "^GSPC",
    }
    fh_symbol = symbol_map.get(symbol, symbol)
    try:
        result = subprocess.run(
            ["curl", "-s", f"https://finnhub.io/api/v1/quote?symbol={fh_symbol}&token={FINNHUB_KEY}"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        if data.get("c", 0) > 0:
            return {
                "price": data.get("c"),
                "change": data.get("d"),
                "change_pct": data.get("dp"),
                "high": data.get("h"),
                "low": data.get("l"),
                "open": data.get("o"),
                "prev_close": data.get("pc"),
            }
    except Exception as e:
        #SILENT_print_(f"  Finnhub error for {symbol}: {e}", file=sys.stderr)
    return None

def fetch_twelvedata_quote(symbol):
    """Fetch quote from Twelve Data (FREE, 800/day, 8/min rate limit)"""
    symbol_map = {
        "BTC": "BTC/USD", "ETH": "ETH/USD", "SOL": "SOL/USD",
        "XRP": "XRP/USD", "DOGE": "DOGE/USD",
        "GOLD": "XAU/USD", "SILVER": "XAG/USD",
        "SP500": "SPY",
    }
    td_symbol = symbol_map.get(symbol, symbol)
    try:
        result = subprocess.run(
            ["curl", "-s", f"https://api.twelvedata.com/quote?symbol={td_symbol}&apikey={TWELVE_DATA_KEY}"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        if data.get("close"):
            return {
                "price": float(data.get("close", 0)),
                "change": float(data.get("change", 0)),
                "change_pct": float(data.get("percent_change", 0)),
                "high": float(data.get("high", 0)),
                "low": float(data.get("low", 0)),
                "open": float(data.get("open", 0)),
                "prev_close": float(data.get("previous_close", 0)),
                "week52_high": float(data.get("fifty_two_week", {}).get("high", 0)),
                "week52_low": float(data.get("fifty_two_week", {}).get("low", 0)),
            }
    except Exception as e:
        #SILENT_print_(f"  TwelveData error for {symbol}: {e}", file=sys.stderr)
    return None

def fetch_twelvedata_ohlcv(symbol, interval="1day", outputsize=30):
    """Fetch daily OHLCV bars from Twelve Data (FREE)"""
    symbol_map = {
        "BTC": "BTC/USD", "ETH": "ETH/USD", "SOL": "SOL/USD",
        "XRP": "XRP/USD", "DOGE": "DOGE/USD",
        "GOLD": "XAU/USD", "SILVER": "XAG/USD",
        "SP500": "SPY",
    }
    td_symbol = symbol_map.get(symbol, symbol)
    try:
        result = subprocess.run(
            ["curl", "-s", f"https://api.twelvedata.com/time_series?symbol={td_symbol}&interval={interval}&outputsize={outputsize}&apikey={TWELVE_DATA_KEY}"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        if data.get("values"):
            bars = []
            for v in data["values"][:20]:  # Last 20 days
                bars.append({
                    "date": v.get("datetime"),
                    "open": float(v.get("open", 0)),
                    "high": float(v.get("high", 0)),
                    "low": float(v.get("low", 0)),
                    "close": float(v.get("close", 0)),
                    "volume": float(v.get("volume", 0)) if v.get("volume") else None,
                })
            return bars
    except Exception as e:
        #SILENT_print_(f"  OHLCV error for {symbol}: {e}", file=sys.stderr)
    return None

# ─── FMP (Financial Modeling Prep) — fundamentals, DCF, technicals ───

def fmp_get(endpoint, params=None):
    """Make an FMP stable API call."""
    params = params or {}
    params["apikey"] = FMP_KEY
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{FMP_BASE}/{endpoint}?{query}"
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", url],
            capture_output=True, text=True, timeout=20
        )
        data = json.loads(result.stdout) if result.stdout else {}
        if isinstance(data, dict) and "Error Message" in data:
            return None
        return data
    except:
        return None

# FMP symbol mapping (our tickers -> FMP symbols)
FMP_SYMBOL_MAP = {
    "GOLD": "GCUSD",     # Gold futures
    "SILVER": "SIUSD",   # Silver futures
    "BTC": "BTCUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "XRP": "XRPUSD",
    "DOGE": "DOGEUSD",
}
# Equities pass through as-is (NVDA -> NVDA)
# SP500 not on FMP directly

def fmp_fetch_quote(symbol):
    """Full real-time quote from FMP with 50/200d MAs, market cap."""
    fmp_sym = FMP_SYMBOL_MAP.get(symbol, symbol)
    data = fmp_get("quote", {"symbol": fmp_sym})
    if not data or not isinstance(data, list) or not data:
        return None
    q = data[0]
    return {
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
        "open": q.get("open", 0),
        "prev_close": q.get("previousClose", 0),
    }

def fmp_fetch_profile(symbol):
    """Company profile from FMP — sector, industry, beta, description."""
    data = fmp_get("profile", {"symbol": symbol})
    if not data or not isinstance(data, list) or not data:
        return None
    p = data[0]
    return {
        "name": p.get("companyName", ""),
        "sector": p.get("sector", ""),
        "industry": p.get("industry", ""),
        "beta": p.get("beta", 0),
        "ceo": p.get("ceo", ""),
        "description": p.get("description", ""),
        "market_cap": p.get("marketCap", 0),
        "employees": p.get("fullTimeEmployees", ""),
        "ipo_date": p.get("ipoDate", ""),
    }

def fmp_fetch_dcf(symbol):
    """DCF intrinsic value from FMP."""
    data = fmp_get("discounted-cash-flow", {"symbol": symbol})
    if not data or not isinstance(data, list) or not data:
        return None
    d = data[0]
    price = d.get("Stock Price", 0)
    dcf = d.get("dcf", 0)
    return {
        "dcf_value": dcf,
        "stock_price": price,
        "upside_pct": ((dcf - price) / price * 100) if price else 0,
    }

def fmp_fetch_financials(symbol):
    """Latest quarterly income statement + balance sheet from FMP."""
    inc = fmp_get("income-statement", {"symbol": symbol, "period": "quarter"})
    bs = fmp_get("balance-sheet-statement", {"symbol": symbol, "period": "quarter"})
    cf = fmp_get("cash-flow-statement", {"symbol": symbol, "period": "quarter"})
    
    result = {"income": [], "balance": [], "cashflow": []}
    
    if inc and isinstance(inc, list):
        for q in inc[:2]:  # Last 2 quarters
            rev = q.get("revenue", 0)
            ni = q.get("netIncome", 0)
            eps = q.get("eps", 0)
            gp = q.get("grossProfit", 0)
            result["income"].append({
                "date": q.get("date", ""),
                "revenue": rev,
                "gross_profit": gp,
                "gross_margin": (gp / rev * 100) if rev else 0,
                "net_income": ni,
                "net_margin": (ni / rev * 100) if rev else 0,
                "eps": eps,
            })
    
    if bs and isinstance(bs, list):
        for q in bs[:2]:
            result["balance"].append({
                "date": q.get("date", ""),
                "assets": q.get("totalAssets", 0),
                "liabilities": q.get("totalLiabilities", 0),
                "equity": q.get("totalStockholdersEquity", 0),
                "cash": q.get("cashAndCashEquivalents", 0),
                "debt": q.get("totalDebt", 0),
            })
    
    if cf and isinstance(cf, list):
        for q in cf[:2]:
            result["cashflow"].append({
                "date": q.get("date", ""),
                "ocf": q.get("operatingCashFlow", 0),
                "fcf": q.get("freeCashFlow", 0),
            })
    
    return result if result["income"] or result["balance"] else None

def fmp_fetch_history(symbol, limit=250):
    """Historical daily prices from FMP. Returns list of {date, close, volume}."""
    fmp_sym = FMP_SYMBOL_MAP.get(symbol, symbol)
    data = fmp_get("historical-price-eod/light", {"symbol": fmp_sym})
    if not data or not isinstance(data, list):
        return None
    for bar in data:
        if "close" not in bar and "price" in bar:
            bar["close"] = bar["price"]
    return data[:limit] if limit > 0 else data

def fmp_compute_rsi(closes, period=14):
    """RSI from list of closes (most recent first)."""
    if len(closes) < period + 1:
        return None
    rev = list(reversed(closes[:period + 1]))
    gains, losses = [], []
    for i in range(1, len(rev)):
        diff = rev[i] - rev[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 1)

def fmp_compute_sma(closes, period):
    """SMA from list of closes (most recent first)."""
    if len(closes) < period:
        return None
    return round(sum(closes[:period]) / period, 2)

def fmp_support_resistance(closes, lookback=90):
    """Support/resistance from pivot detection."""
    if len(closes) < 10:
        return {"support": [], "resistance": []}
    chunk = closes[:lookback] if len(closes) >= lookback else closes
    current = chunk[0]
    supports, resistances = [], []
    w = 5
    for i in range(w, len(chunk) - w):
        left = chunk[i-w:i]
        right = chunk[i+1:i+w+1]
        if chunk[i] == min(left + [chunk[i]] + right):
            supports.append(chunk[i])
        if chunk[i] == max(left + [chunk[i]] + right):
            resistances.append(chunk[i])
    supports = sorted(set([round(s, 2) for s in supports if s < current]), reverse=True)[:3]
    resistances = sorted(set([round(r, 2) for r in resistances if r > current]))[:3]
    return {"current": round(current, 2), "support": supports, "resistance": resistances}

def analyze_trend(bars):
    """Simple discretionary trend analysis from OHLCV bars"""
    if not bars or len(bars) < 5:
        return "Insufficient data for trend analysis"
    
    closes = [b["close"] for b in bars if b["close"] > 0]
    if len(closes) < 5:
        return "Insufficient data"
    
    current = closes[0]  # Most recent first
    avg_5 = sum(closes[:5]) / 5
    avg_20 = sum(closes[:20]) / len(closes[:20]) if len(closes) >= 20 else sum(closes) / len(closes)
    
    # Support/resistance from recent bars
    recent_high = max(b["high"] for b in bars[:10])
    recent_low = min(b["low"] for b in bars[:10])
    
    # Trend determination
    if current > avg_5 > avg_20:
        trend = "UPTREND — price above both 5-day and 20-day moving averages"
    elif current < avg_5 < avg_20:
        trend = "DOWNTREND — price below both moving averages"
    elif current > avg_20 and avg_5 < avg_20:
        trend = "PULLBACK in uptrend — short-term dip but longer trend intact"
    elif current < avg_20 and avg_5 > avg_20:
        trend = "RELIEF RALLY in downtrend — short-term bounce but longer trend down"
    else:
        trend = "RANGE-BOUND — no clear directional bias"
    
    # Position within recent range
    range_pos = ((current - recent_low) / (recent_high - recent_low) * 100) if recent_high != recent_low else 50
    
    # Momentum
    if len(closes) >= 5:
        five_day_change = ((closes[0] - closes[4]) / closes[4]) * 100 if closes[4] > 0 else 0
    else:
        five_day_change = 0
    
    return f"""{trend}
• Current: ${current:,.2f}
• 5-day MA: ${avg_5:,.2f} | 20-day MA: ${avg_20:,.2f}
• 10-day range: ${recent_low:,.2f} - ${recent_high:,.2f}
• Position in range: {range_pos:.0f}% (0%=bottom, 100%=top)
• 5-day momentum: {five_day_change:+.1f}%"""

def fetch_av_technicals(symbol):
    """Fetch pre-computed technicals from Alpha Vantage (RSI, SMA, ADX, ATR, BBANDS).
    Free tier: 25 req/day, 1 req/sec. Uses 5 requests per symbol."""
    import time
    result = {}
    
    def av_get(function, extra_params=""):
        url = f"{AV_BASE}?function={function}&symbol={symbol}&interval=daily{extra_params}&apikey={AV_KEY}"
        try:
            r = requests.get(url, timeout=15)
            return r.json()
        except:
            return {}
    
    # RSI
    data = av_get("RSI", "&time_period=14&series_type=close")
    ta = data.get("Technical Analysis: RSI", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        result["rsi"] = float(ta[k]["RSI"])
    time.sleep(1.5)
    
    # SMA 20
    data = av_get("SMA", "&time_period=20&series_type=close")
    ta = data.get("Technical Analysis: SMA", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        result["sma20"] = float(ta[k]["SMA"])
    time.sleep(1.5)
    
    # SMA 50
    data = av_get("SMA", "&time_period=50&series_type=close")
    ta = data.get("Technical Analysis: SMA", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        result["sma50"] = float(ta[k]["SMA"])
    time.sleep(1.5)
    
    # SMA 200
    data = av_get("SMA", "&time_period=200&series_type=close")
    ta = data.get("Technical Analysis: SMA", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        result["sma200"] = float(ta[k]["SMA"])
    time.sleep(1.5)
    
    # ADX
    data = av_get("ADX", "&time_period=14")
    ta = data.get("Technical Analysis: ADX", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        result["adx"] = float(ta[k]["ADX"])
    time.sleep(1.5)
    
    # ATR
    data = av_get("ATR", "&time_period=14")
    ta = data.get("Technical Analysis: ATR", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        result["atr"] = float(ta[k]["ATR"])
    time.sleep(1.5)
    
    # BBANDS
    data = av_get("BBANDS", "&time_period=20&series_type=close")
    ta = data.get("Technical Analysis: BBANDS", {})
    if ta:
        k = sorted(ta.keys(), reverse=True)[0]
        v = ta[k]
        result["bb_upper"] = float(v["Real Upper Band"])
        result["bb_mid"] = float(v["Real Middle Band"])
        result["bb_lower"] = float(v["Real Lower Band"])
    
    return result if "rsi" in result else None


def generate_analysis(ticker, coingecko_quotes=None):
    """Generate a complete ticker analysis"""
    now = datetime.now(timezone.utc)
    
    # For crypto tickers, try CoinGecko first (free, fast, batch)
    quote = None
    source = None
    
    if ticker in COINGECKO_IDS and coingecko_quotes and ticker in coingecko_quotes:
        quote = coingecko_quotes[ticker]
        source = "CoinGecko"
    
    # Fall back to Finnhub, then Twelve Data
    if not quote:
        quote = fetch_finnhub_quote(ticker)
        source = "Finnhub"
    
    if not quote:
        quote = fetch_twelvedata_quote(ticker)
        source = "Twelve Data"
    
    if not quote:
        return None
    
    # Get OHLCV for technical analysis — CoinGecko for crypto, Twelve Data for rest
    if ticker in COINGECKO_IDS:
        bars = fetch_coingecko_ohlc(ticker)
    else:
        bars = fetch_twelvedata_ohlcv(ticker)
    trend_analysis = analyze_trend(bars) if bars else "Technical data unavailable"
    
    # Build the analysis
    price = quote.get("price", 0)
    change = quote.get("change", 0)
    change_pct = quote.get("change_pct", 0)
    
    # 52-week data if available
    week52 = ""
    if quote.get("week52_high"):
        week52 = f"""
**52-Week Range:** ${quote['week52_low']:,.2f} - ${quote['week52_high']:,.2f}
**Distance from 52w high:** {((price - quote['week52_high']) / quote['week52_high'] * 100):+.1f}%"""
    
    # Determine asset class
    crypto_tickers = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
    commodity_tickers = ["GOLD", "SILVER"]
    is_equity = ticker not in crypto_tickers and ticker not in commodity_tickers and ticker != "SP500"
    asset_class = "Crypto" if ticker in crypto_tickers else "Commodity" if ticker in commodity_tickers else "Index" if ticker == "SP500" else "Equity"
    
    # Fetch analyst ratings and earnings for equities only
    analyst_section = ""
    earnings_section = ""
    if is_equity:
        ratings = fetch_finnhub_analyst_ratings(ticker)
        if ratings:
            analyst_section = f"""
## 📊 Analyst Consensus
**Rating:** {ratings['consensus']} ({ratings['bull_pct']:.0f}% bullish)
**Breakdown:** {ratings['strong_buy']} Strong Buy · {ratings['buy']} Buy · {ratings['hold']} Hold · {ratings['sell']} Sell · {ratings['strong_sell']} Strong Sell
**Total Analysts:** {ratings['total']}"""
        
        earnings = fetch_finnhub_earnings(ticker)
        if earnings:
            eps_str = f"${earnings['eps_estimate']:.2f}" if earnings.get('eps_estimate') else "N/A"
            earnings_section = f"""
## 📅 Next Earnings
**Date:** {earnings['date']}
**EPS Estimate:** {eps_str}"""
    
    # ─── FMP ENHANCEMENT: Fundamentals + DCF + Technicals ───
    fmp_section = ""
    fmp_tech_section = ""
    
    if is_equity:
        # DCF valuation
        dcf = fmp_fetch_dcf(ticker)
        dcf_str = ""
        if dcf:
            verdict = "UNDERVALUED" if dcf["upside_pct"] > 15 else "OVERVALUED" if dcf["upside_pct"] < -15 else "FAIRLY VALUED"
            dcf_str = f"""
## 💰 DCF Valuation (FMP)
**Intrinsic Value:** ${dcf['dcf_value']:,.2f}
**Market Price:** ${dcf['stock_price']:,.2f}
**Upside to Fair Value:** {dcf['upside_pct']:+.1f}%
**Verdict:** {verdict}"""
        
        # Financials
        fins = fmp_fetch_financials(ticker)
        fin_str = ""
        if fins and fins["income"]:
            q = fins["income"][0]
            fin_str = f"""
## 📑 Fundamentals (FMP — Latest Quarter)
**Revenue:** ${q['revenue']/1e9:.1f}B | **Gross Margin:** {q['gross_margin']:.1f}% | **Net Margin:** {q['net_margin']:.1f}% | **EPS:** ${q['eps']:.2f}"""
            if fins["balance"]:
                b = fins["balance"][0]
                debt_str = f"${b['debt']/1e9:.1f}B" if b['debt'] else "N/A"
                cash_str = f"${b['cash']/1e9:.1f}B" if b['cash'] else "N/A"
                fin_str += f"\n**Assets:** ${b['assets']/1e9:.1f}B | **Equity:** ${b['equity']/1e9:.1f}B | **Cash:** {cash_str} | **Debt:** {debt_str}"
            if fins["cashflow"]:
                c = fins["cashflow"][0]
                fcf_str = f"${c['fcf']/1e9:.1f}B" if c['fcf'] else "N/A"
                fin_str += f"\n**Operating CF:** ${c['ocf']/1e9:.1f}B | **Free CF:** {fcf_str}"
        
        # FMP historical technicals (RSI, SMAs, support/resistance)
        # Alpha Vantage for pre-computed technicals (more accurate than manual computation)
        av_tech = fetch_av_technicals(ticker)
        if av_tech:
            rsi_str = f"{av_tech['rsi']:.1f} ({'Overbought' if av_tech['rsi'] > 70 else 'Oversold' if av_tech['rsi'] < 30 else 'Neutral'})"
            sma50_str = f"${av_tech['sma50']:,.2f}" if av_tech.get('sma50') else "N/A"
            sma200_str = f"${av_tech['sma200']:,.2f}" if av_tech.get('sma200') else "N/A"
            adx_str = f"{av_tech['adx']:.1f} ({'Strong trend' if av_tech['adx'] > 25 else 'Weak/no trend'})" if av_tech.get('adx') else "N/A"
            atr_str = f"${av_tech['atr']:,.2f}" if av_tech.get('atr') else "N/A"
            bb_str = f"Upper ${av_tech['bb_upper']:,.2f} | Mid ${av_tech['bb_mid']:,.2f} | Lower ${av_tech['bb_lower']:,.2f}" if av_tech.get('bb_upper') else "N/A"
            
            fmp_tech_section = f"""
## 📐 Technicals (Alpha Vantage + FMP)
**RSI(14):** {rsi_str}
**SMA-20:** ${av_tech['sma20']:,.2f} | **SMA-50:** {sma50_str} | **SMA-200:** {sma200_str}
**ADX(14):** {adx_str} | **ATR(14):** {atr_str}
**Bollinger Bands:** {bb_str}"""
            
            # Add support/resistance from FMP historical data
            hist = fmp_fetch_history(ticker, 250)
            if hist and len(hist) >= 20:
                closes = [bar.get("close", 0) for bar in hist]
                sr = fmp_support_resistance(closes, 90)
                res_str = ", ".join(f"${r:,.2f}" for r in sr["resistance"]) if sr["resistance"] else "None"
                sup_str = ", ".join(f"${s:,.2f}" for s in sr["support"]) if sr["support"] else "None"
                fmp_tech_section += f"\n**Resistance:** {res_str}\n**Support:** {sup_str}"
        else:
            # Fallback to FMP-computed technicals
            hist = fmp_fetch_history(ticker, 250)
            if hist and len(hist) >= 20:
                closes = [bar.get("close", 0) for bar in hist]
                rsi = fmp_compute_rsi(closes, 14)
                sma_20 = fmp_compute_sma(closes, 20)
                sma_50 = fmp_compute_sma(closes, 50) if len(closes) >= 50 else None
                sma_200 = fmp_compute_sma(closes, 200) if len(closes) >= 200 else None
                sr = fmp_support_resistance(closes, 90)
                
                rsi_str = f"{rsi:.1f} ({'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'})" if rsi else "N/A"
                sma50_str = f"${sma_50:,.2f}" if sma_50 else "N/A"
                sma200_str = f"${sma_200:,.2f}" if sma_200 else "N/A"
                res_str = ", ".join(f"${r:,.2f}" for r in sr["resistance"]) if sr["resistance"] else "None"
                sup_str = ", ".join(f"${s:,.2f}" for s in sr["support"]) if sr["support"] else "None"
                
                fmp_tech_section = f"""
## 📐 FMP Technicals (Daily Chart)
**RSI(14):** {rsi_str}
**SMA-20:** ${sma_20:,.2f} | **SMA-50:** {sma50_str} | **SMA-200:** {sma200_str}
**Resistance:** {res_str}
**Support:** {sup_str}"""
        
        fmp_section = f"{dcf_str}{fin_str}{fmp_tech_section}"
    
    direction = "🟢" if change >= 0 else "🔴"
    
    analysis = f"""🧠 **{ticker} — Big Brain Ape Analysis**
*Generated: {now.strftime('%b %d, %Y %H:%M UTC')} | Source: {source}*

## 📊 Price Action
**Current:** ${price:,.2f} {direction} {change:+,.2f} ({change_pct:+.2f}%)
**Day Range:** ${quote.get('low', 0):,.2f} - ${quote.get('high', 0):,.2f}
**Prev Close:** ${quote.get('prev_close', 0):,.2f}{week52}
{analyst_section}{earnings_section}{fmp_section}

## 📈 Technical Structure (20-day)
{trend_analysis}

## 🎯 Macro Context
Asset class: {asset_class}
• This analysis is auto-generated from real-time data
• For full autonomous trading bot analysis with Fed/liquidity/valuation lens, reply with "DEEP {ticker}"

---
⚠️ Not financial advice. Markets are risky. Do your own research.
*Powered by free data: Finnhub + Twelve Data + CoinGecko + FRED + FMP + Alpha Vantage*"""

    return analysis

def main():
    #SILENT_print_(f"Ticker cache generation started at {datetime.now(timezone.utc).isoformat()}")
    #SILENT_print_(f"Cache dir: {CACHE_DIR}")
    #SILENT_print_(f"Tickers: {len(TICKERS)}")
    #SILENT_print_("")
    
    success = 0
    failed = 0
    
    # Pre-fetch ALL crypto quotes from CoinGecko in ONE batch call (free, fast)
    crypto_tickers = [t for t in TICKERS if t in COINGECKO_IDS]
    #SILENT_print_(f"Fetching {len(crypto_tickers)} crypto quotes from CoinGecko (1 batch call)...")
    coingecko_quotes = fetch_coingecko_quote(crypto_tickers)
    if coingecko_quotes:
        #SILENT_print_(f"  Got {len(coingecko_quotes)} quotes: {', '.join(coingecko_quotes.keys())}")
    else:
        #SILENT_print_("  CoinGecko unavailable, will fall back to Finnhub/Twelve Data")
    #SILENT_print_()
    
    # Twelve Data rate limit: 8 calls/min on free tier
    # With CoinGecko handling crypto, TD is only needed for:
    #   - Equity OHLCV (1 call each): NVDA, TSLA, AAPL, MSFT, AMZN, META, GOOGL, AMD, COIN, HOOD, MSTR, PLTR = 12 calls
    #   - GOLD + SP500 OHLCV (1 call each) = 2 calls (quote from Finnhub)
    # Total TD calls: ~14, so 2 rate-limit waits instead of 5
    td_call_count = 0
    td_batch_limit = 7
    td_quote_tickers = {"GOLD", "SP500"}  # Only non-crypto that need TD for quotes
    
    for ticker in TICKERS:
        #SILENT_print_(f"Generating {ticker}...", end=" ", flush=True)
        
        # Estimate TD calls: 0 for crypto (CoinGecko), 1 for equity OHLCV, 2 for GOLD/SP500
        if ticker in COINGECKO_IDS:
            estimated_td_calls = 0
        elif ticker in td_quote_tickers:
            estimated_td_calls = 2
        else:
            estimated_td_calls = 1
        
        # Check if we need to wait for Twelve Data rate limit
        if estimated_td_calls > 0 and td_call_count + estimated_td_calls > td_batch_limit:
            #SILENT_print_(f"\n  (Waiting 65s for Twelve Data rate limit reset...)", flush=True)
            import time
            time.sleep(65)
            td_call_count = 0
        
        try:
            analysis = generate_analysis(ticker, coingecko_quotes)
            if analysis:
                filepath = os.path.join(CACHE_DIR, f"{ticker}.md")
                with open(filepath, "w") as f:
                    f.write(analysis)
                #SILENT_print_("✅")
                success += 1
                td_call_count += estimated_td_calls
            else:
                #SILENT_print_("❌ (no data)")
                failed += 1
                td_call_count += estimated_td_calls
        except Exception as e:
            #SILENT_print_(f"❌ ({e})")
            failed += 1
            td_call_count += estimated_td_calls
    
    #SILENT_print_("")
    #SILENT_print_(f"Done: {success} cached, {failed} failed")
    
    # Save metadata
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tickers_cached": success,
        "tickers_failed": failed,
        "cached_tickers": [t for t in TICKERS if os.path.exists(os.path.join(CACHE_DIR, f"{t}.md"))],
    }
    with open(os.path.join(CACHE_DIR, "_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    
    # Output summary for cron delivery (only if something failed)
    if failed > 0:
        #SILENT_print_(f"\n⚠️ {failed} tickers failed to cache. Check data source availability.")
        sys.exit(1)
    else:
        # Silent on success — zero compute
        sys.exit(0)

if __name__ == "__main__":
    main()
