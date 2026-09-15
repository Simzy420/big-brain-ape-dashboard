"""
Yahoo Finance Data Tool — Free, no API key required.
pip install yfinance

Provides:
  1. get_yahoo_data() — Quick snapshot: price, daily change, volume, 52-week range
  2. get_yahoo_history() — Full OHLCV dataframe for charting/backtesting
  3. get_yahoo_quote_table() — Full quote table with market cap, P/E, EPS, etc.
  4. get_yahoo_options() — Options chain expiry dates (for options flow analysis)
  5. get_yahoo_news() — Asset-specific news headlines from Yahoo Finance

Usage:
    from yahoo_data import get_yahoo_data, get_yahoo_history, get_yahoo_quote_table
    
    # Quick price snapshot
    data = get_yahoo_data("NVDA")
    
    # Full history for charting
    history = get_yahoo_history("BTC-USD", period="1y")
    
    # Full quote table (fundamentals)
    quote = get_yahoo_quote_table("NVDA")

Yahoo Finance Symbol Reference:
    Stocks:   NVDA, TSLA, AAPL, MSFT, AMZN, META, etc.
    Crypto:   BTC-USD, ETH-USD, SOL-USD
    Futures:  BZ=F (Brent), CL=F (WTI), GC=F (Gold), SI=F (Silver), NG=F (NatGas)
    Indices:  ^GSPC (S&P 500), ^IXIC (Nasdaq), ^DJI (Dow), ^VIX
    FX:       DX-Y.NYB (DXY), EURUSD=X, JPY=X
    ETFs:     GLD, USO, XLK, XLF
"""

import yfinance as yf
import pandas as pd


def get_yahoo_data(symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
    """
    Quick price snapshot with daily change, volume, and 52-week range.
    
    Returns: {symbol, price, change_percent, volume, high_52w, low_52w}
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        return {"error": f"No data for {symbol}"}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    return {
        "symbol": symbol,
        "price": round(float(latest["Close"]), 2),
        "change_percent": round(((latest["Close"] - prev["Close"]) / prev["Close"]) * 100, 2),
        "volume": int(latest["Volume"]),
        "high_52w": round(float(df["High"].max()), 2),
        "low_52w": round(float(df["Low"].min()), 2)
    }


def get_yahoo_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Full OHLCV history dataframe for charting, backtesting, or custom analysis.
    
    Periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    Intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    return df


def get_yahoo_quote_table(symbol: str) -> dict:
    """
    Full quote table with fundamentals: market cap, P/E, EPS, dividend yield,
    beta, profit margins, ROE, debt-to-equity, and more.
    
    Useful for the Valuation lens in the Druckenmiller framework.
    """
    ticker = yf.Ticker(symbol)
    info = ticker.info
    
    result = {
        "symbol": symbol,
        "name": info.get("shortName", info.get("longName", "N/A")),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "enterprise_value": info.get("enterpriseValue", "N/A"),
        "trailing_pe": info.get("trailingPE", "N/A"),
        "forward_pe": info.get("forwardPE", "N/A"),
        "peg_ratio": info.get("pegRatio", "N/A"),
        "price_to_sales": info.get("priceToSalesTrailing12Months", "N/A"),
        "price_to_book": info.get("priceToBook", "N/A"),
        "enterprise_to_revenue": info.get("enterpriseToRevenue", "N/A"),
        "enterprise_to_ebitda": info.get("enterpriseToEbitda", "N/A"),
        "profit_margins": info.get("profitMargins", "N/A"),
        "gross_margins": info.get("grossMargins", "N/A"),
        "operating_margins": info.get("operatingMargins", "N/A"),
        "return_on_equity": info.get("returnOnEquity", "N/A"),
        "return_on_assets": info.get("returnOnAssets", "N/A"),
        "debt_to_equity": info.get("debtToEquity", "N/A"),
        "current_ratio": info.get("currentRatio", "N/A"),
        "quick_ratio": info.get("quickRatio", "N/A"),
        "total_cash": info.get("totalCash", "N/A"),
        "total_debt": info.get("totalDebt", "N/A"),
        "revenue_growth": info.get("revenueGrowth", "N/A"),
        "earnings_growth": info.get("earningsGrowth", "N/A"),
        "dividend_yield": info.get("dividendYield", "N/A"),
        "beta": info.get("beta", "N/A"),
        "fifty_day_avg": info.get("fiftyDayAverage", "N/A"),
        "two_hundred_day_avg": info.get("twoHundredDayAverage", "N/A"),
        "analyst_target_low": info.get("targetLowPrice", "N/A"),
        "analyst_target_mean": info.get("targetMeanPrice", "N/A"),
        "analyst_target_median": info.get("targetMedianPrice", "N/A"),
        "analyst_target_high": info.get("targetHighPrice", "N/A"),
        "analyst_recommendation": info.get("recommendationKey", "N/A"),
        "analyst_count": info.get("numberOfAnalystOpinions", "N/A"),
    }
    
    # Format large numbers
    if isinstance(result["market_cap"], (int, float)) and result["market_cap"] > 1e9:
        result["market_cap_fmt"] = f"${result['market_cap']/1e9:.1f}B"
    elif isinstance(result["market_cap"], (int, float)) and result["market_cap"] > 1e6:
        result["market_cap_fmt"] = f"${result['market_cap']/1e6:.1f}M"
    
    # Format percentages
    for pct_key in ["profit_margins", "gross_margins", "operating_margins", 
                     "return_on_equity", "return_on_assets", "revenue_growth", 
                     "earnings_growth", "dividend_yield"]:
        val = result.get(pct_key)
        if isinstance(val, float):
            result[f"{pct_key}_fmt"] = f"{val*100:.1f}%"
    
    return result


def get_yahoo_news(symbol: str) -> list:
    """
    Get Yahoo Finance news headlines for a specific symbol.
    Complements the DuckDuckGo search with Yahoo's curated financial news.
    """
    ticker = yf.Ticker(symbol)
    news = ticker.news
    
    results = []
    if news:
        for item in news[:10]:
            results.append({
                "title": item.get("title", "N/A"),
                "publisher": item.get("publisher", "N/A"),
                "link": item.get("link", "N/A"),
                "published": item.get("providerPublishTime", "N/A"),
                "type": item.get("type", "N/A"),
            })
    
    return results


def get_multi_snapshot(symbols: list) -> dict:
    """Get quick price snapshots for multiple symbols at once."""
    results = {}
    for sym in symbols:
        try:
            results[sym] = get_yahoo_data(sym)
        except Exception as e:
            results[sym] = {"error": str(e)}
    return results


def format_snapshot(data: dict) -> str:
    """Format a price snapshot for display."""
    if "error" in data:
        return f"ERROR: {data['error']}"
    
    change_str = f"+{data['change_percent']}%" if data['change_percent'] >= 0 else f"{data['change_percent']}%"
    vol_str = f"{data['volume']:,}" if data['volume'] > 0 else "N/A"
    
    return (f"{data['symbol']}: ${data['price']} ({change_str}) | "
            f"52w: ${data['low_52w']}-${data['high_52w']} | Vol: {vol_str}")


def format_quote_table(quote: dict) -> str:
    """Format the full quote table for display."""
    if "error" in quote:
        return f"ERROR: {quote['error']}"
    
    lines = []
    lines.append(f"{quote.get('name', quote['symbol'])} ({quote['symbol']})")
    lines.append(f"  Sector: {quote.get('sector', 'N/A')} | Industry: {quote.get('industry', 'N/A')}")
    
    if quote.get("market_cap_fmt"):
        lines.append(f"  Market Cap: {quote['market_cap_fmt']}")
    
    lines.append(f"  P/E (trailing): {quote.get('trailing_pe', 'N/A')} | P/E (forward): {quote.get('forward_pe', 'N/A')}")
    lines.append(f"  PEG Ratio: {quote.get('peg_ratio', 'N/A')} | P/S: {quote.get('price_to_sales', 'N/A')} | P/B: {quote.get('price_to_book', 'N/A')}")
    lines.append(f"  Profit Margin: {quote.get('profit_margins_fmt', quote.get('profit_margins', 'N/A'))} | Gross Margin: {quote.get('gross_margins_fmt', quote.get('gross_margins', 'N/A'))}")
    lines.append(f"  ROE: {quote.get('return_on_equity_fmt', quote.get('return_on_equity', 'N/A'))} | ROA: {quote.get('return_on_assets_fmt', quote.get('return_on_assets', 'N/A'))}")
    lines.append(f"  Revenue Growth: {quote.get('revenue_growth_fmt', quote.get('revenue_growth', 'N/A'))} | Earnings Growth: {quote.get('earnings_growth_fmt', quote.get('earnings_growth', 'N/A'))}")
    lines.append(f"  Debt/Equity: {quote.get('debt_to_equity', 'N/A')} | Current Ratio: {quote.get('current_ratio', 'N/A')}")
    lines.append(f"  Beta: {quote.get('beta', 'N/A')} | Div Yield: {quote.get('dividend_yield_fmt', quote.get('dividend_yield', 'N/A'))}")
    lines.append(f"  50-day MA: ${quote.get('fifty_day_avg', 'N/A')} | 200-day MA: ${quote.get('two_hundred_day_avg', 'N/A')}")
    
    target_mean = quote.get("analyst_target_mean", "N/A")
    target_low = quote.get("analyst_target_low", "N/A")
    target_high = quote.get("analyst_target_high", "N/A")
    rec = quote.get("analyst_recommendation", "N/A")
    lines.append(f"  Analyst Target: Low ${target_low} | Mean ${target_mean} | High ${target_high}")
    lines.append(f"  Analyst Recommendation: {rec} ({quote.get('analyst_count', 0)} analysts)")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("YAHOO FINANCE DATA TOOL — TEST")
    print("=" * 60)
    
    # Test 1: Quick snapshots on current portfolio
    print("\n--- Price Snapshots ---")
    symbols = ["BZ=F", "GC=F", "^GSPC", "BTC-USD", "NVDA", "DX-Y.NYB"]
    for sym in symbols:
        data = get_yahoo_data(sym)
        print(f"  {format_snapshot(data)}")
    
    # Test 2: Full quote table on NVDA (our former position)
    print("\n--- NVDA Full Quote Table ---")
    quote = get_yahoo_quote_table("NVDA")
    print(format_quote_table(quote))
    
    # Test 3: Quick quote on a few more
    print("\n--- TSLA Quote ---")
    tsla = get_yahoo_quote_table("TSLA")
    print(format_quote_table(tsla))
