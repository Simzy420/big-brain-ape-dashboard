"""
Technical Analysis Tool — Powered by pandas-ta + yfinance
Free, no API key required.

Indicators included:
  - EMA (50, 100, 200) — trend direction
  - RSI (14) — momentum / overbought-oversold
  - MACD — momentum crossover
  - Bollinger Bands (20, 2) — volatility envelope
  - Bollinger Band Squeeze — breakout detection
  - ATR (14) — volatility for position sizing
  - SMA (20) — short-term trend
  - Stochastic (14, 3, 3) — momentum confirmation
  - ADX (14) — trend STRENGTH (not direction)
  - OBV — volume-based accumulation/distribution
  - Volume analysis — smart money detection
  - Fibonacci Retracement — key support/resistance levels
  - Support/Resistance — auto-detected from recent swings

Usage:
    from ta_analysis import get_technical_analysis
    result = get_technical_analysis("NVDA")
    result = get_technical_analysis("BTC-USD")
    result = get_technical_analysis("CL=F")          # Oil (WTI)
    result = get_technical_analysis("GC=F")          # Gold futures
    result = get_technical_analysis("BZ=F")          # Brent Oil
    result = get_technical_analysis("DX-Y.NYB")      # DXY Dollar Index
    result = get_technical_analysis("^GSPC")         # S&P 500
"""

import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import numpy as np


def get_technical_analysis(symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
    """
    Gets price data + full technical indicator suite for a stock or crypto.

    Examples:
        get_technical_analysis("NVDA")
        get_technical_analysis("BTC-USD")
        get_technical_analysis("CL=F")          # Oil
        get_technical_analysis("GC=F")          # Gold
    """

    # Download data
    df = yf.download(symbol, period=period, interval=interval, progress=False)

    if df.empty:
        return {"error": f"No data found for {symbol}"}

    # Fix multi-index columns if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # ===== Add Technical Indicators =====
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=100, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.bbands(length=20, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.sma(length=20, append=True)

    # New indicators
    df.ta.stoch(length=14, k=3, d=3, append=True)   # Stochastic
    df.ta.adx(length=14, append=True)                # Trend strength
    df.ta.obv(append=True)                           # On-Balance Volume

    # Get the latest row
    latest = df.iloc[-1]

    result = {
        "symbol": symbol,
        "price": round(float(latest["Close"]), 2),
        "ema_50": round(float(latest["EMA_50"]), 2) if "EMA_50" in latest and pd.notna(latest["EMA_50"]) else None,
        "ema_100": round(float(latest["EMA_100"]), 2) if "EMA_100" in latest and pd.notna(latest["EMA_100"]) else None,
        "ema_200": round(float(latest["EMA_200"]), 2) if "EMA_200" in latest and pd.notna(latest["EMA_200"]) else None,
        "rsi_14": round(float(latest["RSI_14"]), 2) if "RSI_14" in latest and pd.notna(latest["RSI_14"]) else None,
        "macd": round(float(latest["MACD_12_26_9"]), 4) if "MACD_12_26_9" in latest and pd.notna(latest["MACD_12_26_9"]) else None,
        "macd_signal": round(float(latest["MACDs_12_26_9"]), 4) if "MACDs_12_26_9" in latest and pd.notna(latest["MACDs_12_26_9"]) else None,
        "atr_14": round(float(latest["ATRr_14"]), 2) if "ATRr_14" in latest and pd.notna(latest["ATRr_14"]) else None,
        "sma_20": round(float(latest["SMA_20"]), 2) if "SMA_20" in latest and pd.notna(latest["SMA_20"]) else None,
    }

    # ===== Bollinger Bands =====
    if "BBU_20_2.0" in latest and pd.notna(latest["BBU_20_2.0"]):
        result["bb_upper"] = round(float(latest["BBU_20_2.0"]), 2)
        result["bb_lower"] = round(float(latest["BBL_20_2.0"]), 2)
        result["bb_mid"] = round(float(latest["BBM_20_2.0"]), 2)
        result["bb_width"] = round(result["bb_upper"] - result["bb_lower"], 2)

        # Where is price within the bands? (0 = lower band, 1 = upper band)
        bb_range = result["bb_upper"] - result["bb_lower"]
        if bb_range > 0:
            result["bb_position"] = round((result["price"] - result["bb_lower"]) / bb_range, 2)

    # ===== Bollinger Band Squeeze Detection =====
    # A squeeze happens when the band width narrows to its lowest point in a while.
    # This often precedes a major breakout — the longer the squeeze, the bigger the move.
    bb_width_col = df["BBU_20_2.0"] - df["BBL_20_2.0"] if "BBU_20_2.0" in df.columns else None
    if bb_width_col is not None and len(bb_width_col) >= 60:
        # Compare current width to the last 60 days
        recent_widths = bb_width_col.dropna().tail(60)
        if len(recent_widths) >= 20:
            current_width = float(recent_widths.iloc[-1])
            avg_width = float(recent_widths.mean())
            min_width = float(recent_widths.min())
            max_width = float(recent_widths.max())

            # Squeeze ratio: how tight are the bands relative to average?
            squeeze_ratio = current_width / avg_width if avg_width > 0 else 1.0
            result["squeeze_ratio"] = round(squeeze_ratio, 2)

            # Find how many days the bands have been narrowing
            narrowing_days = 0
            for i in range(len(recent_widths) - 1, 0, -1):
                if recent_widths.iloc[i] <= recent_widths.iloc[i - 1]:
                    narrowing_days += 1
                else:
                    break
            result["squeeze_days"] = narrowing_days

            if squeeze_ratio < 0.75:
                result["squeeze_status"] = "SQUEEZE — Breakout imminent"
            elif squeeze_ratio < 0.90:
                result["squeeze_status"] = "Tightening — Watch for breakout"
            elif squeeze_ratio > 1.5:
                result["squeeze_status"] = "Expanding — Trend in progress"
            else:
                result["squeeze_status"] = "Normal range"

    # ===== Stochastic Oscillator =====
    if "STOCHk_14_3_3" in latest and pd.notna(latest["STOCHk_14_3_3"]):
        result["stoch_k"] = round(float(latest["STOCHk_14_3_3"]), 2)
        result["stoch_d"] = round(float(latest["STOCHd_14_3_3"]), 2)

        if result["stoch_k"] > 80:
            result["stoch_signal"] = "Overbought"
        elif result["stoch_k"] < 20:
            result["stoch_signal"] = "Oversold"
        elif result["stoch_k"] > result["stoch_d"]:
            result["stoch_signal"] = "Bullish cross"
        else:
            result["stoch_signal"] = "Bearish cross"

    # ===== ADX (Trend Strength) =====
    if "ADX_14" in latest and pd.notna(latest["ADX_14"]):
        result["adx_14"] = round(float(latest["ADX_14"]), 2)

        if result["adx_14"] > 50:
            result["adx_signal"] = "Extremely strong trend"
        elif result["adx_14"] > 25:
            result["adx_signal"] = "Strong trend — hold winners"
        elif result["adx_14"] > 20:
            result["adx_signal"] = "Developing trend"
        else:
            result["adx_signal"] = "Weak / no trend — range-bound"

    # ===== OBV (On-Balance Volume) =====
    if "OBV" in latest and pd.notna(latest["OBV"]):
        result["obv"] = round(float(latest["OBV"]), 0)

        # Compare OBV trend to price trend (divergence detection)
        obv_20_ago = float(df["OBV"].iloc[-21]) if len(df) > 21 and pd.notna(df["OBV"].iloc[-21]) else None
        price_20_ago = float(df["Close"].iloc[-21]) if len(df) > 21 else None

        if obv_20_ago is not None and price_20_ago is not None:
            price_change = (result["price"] - price_20_ago) / price_20_ago
            obv_change = (result["obv"] - obv_20_ago) / abs(obv_20_ago) if obv_20_ago != 0 else 0

            if price_change > 0 and obv_change < 0:
                result["obv_signal"] = "BEARISH DIVERGENCE — price up but volume says distribution"
            elif price_change < 0 and obv_change > 0:
                result["obv_signal"] = "BULLISH DIVERGENCE — price down but volume says accumulation"
            elif price_change > 0 and obv_change > 0:
                result["obv_signal"] = "Confirmed — volume confirms the move"
            else:
                result["obv_signal"] = "Confirmed — volume confirms the decline"

    # ===== Volume Analysis =====
    if "Volume" in df.columns and len(df) >= 20:
        latest_volume = float(latest["Volume"])
        avg_volume_20 = float(df["Volume"].tail(20).mean())

        if avg_volume_20 > 0:
            result["volume"] = round(latest_volume, 0)
            result["avg_volume_20"] = round(avg_volume_20, 0)
            result["volume_ratio"] = round(latest_volume / avg_volume_20, 2)

            if result["volume_ratio"] > 2.0:
                result["volume_signal"] = "EXPLOSION — 2x+ average volume, major event"
            elif result["volume_ratio"] > 1.5:
                result["volume_signal"] = "High — institutional activity"
            elif result["volume_ratio"] > 1.0:
                result["volume_signal"] = "Above average"
            elif result["volume_ratio"] < 0.5:
                result["volume_signal"] = "Very low — no conviction"
            else:
                result["volume_signal"] = "Normal"

    # ===== Fibonacci Retracement Levels =====
    # Find the recent swing high and swing low over the lookback period
    # Then compute standard Fib levels (23.6%, 38.2%, 50%, 61.8%, 78.6%)
    lookback = min(len(df), 90)  # Use up to 90 days
    recent = df.tail(lookback)

    swing_high = float(recent["High"].max())
    swing_low = float(recent["Low"].min())
    swing_range = swing_high - swing_low

    if swing_range > 0:
        # Determine if we're in an uptrend or downtrend (where did the swing start?)
        high_idx = recent["High"].idxmax()
        low_idx = recent["Low"].idxmin()

        if high_idx > low_idx:
            # High came after low = uptrend, retracements measured from low to high
            fib_direction = "uptrend"
            fib_levels = {
                "fib_236": round(swing_high - swing_range * 0.236, 2),   # 23.6% retracement
                "fib_382": round(swing_high - swing_range * 0.382, 2),   # 38.2% retracement
                "fib_500": round(swing_high - swing_range * 0.500, 2),   # 50.0% retracement
                "fib_618": round(swing_high - swing_range * 0.618, 2),   # 61.8% retracement (golden ratio)
                "fib_786": round(swing_high - swing_range * 0.786, 2),   # 78.6% retracement
            }
        else:
            # Low came after high = downtrend, retracements measured from high to low
            fib_direction = "downtrend"
            fib_levels = {
                "fib_236": round(swing_low + swing_range * 0.236, 2),
                "fib_382": round(swing_low + swing_range * 0.382, 2),
                "fib_500": round(swing_low + swing_range * 0.500, 2),
                "fib_618": round(swing_low + swing_range * 0.618, 2),
                "fib_786": round(swing_low + swing_range * 0.786, 2),
            }

        result["fib_direction"] = fib_direction
        result["fib_swing_high"] = round(swing_high, 2)
        result["fib_swing_low"] = round(swing_low, 2)
        result.update(fib_levels)

        # Where is current price relative to Fib levels?
        # Find the closest Fib level
        fib_names = {
            "fib_236": "23.6%",
            "fib_382": "38.2%",
            "fib_500": "50.0%",
            "fib_618": "61.8% (Golden)",
            "fib_786": "78.6%",
        }
        closest_fib = None
        closest_dist = float('inf')
        for key, label in fib_names.items():
            if key in result:
                dist = abs(result["price"] - result[key])
                if dist < closest_dist:
                    closest_dist = dist
                    closest_fib = label

        if closest_fib:
            result["fib_nearest"] = f"{closest_fib} (${closest_dist:.2f} away)"

    # ===== Support / Resistance (recent swing points) =====
    # Simple approach: find recent local highs and lows
    if len(df) >= 20:
        recent_30 = df.tail(30)
        # Resistance = recent highs that price has struggled to break
        resistance = float(recent_30["High"].nlargest(3).mean())
        # Support = recent lows where price has bounced
        support = float(recent_30["Low"].nsmallest(3).mean())

        result["resistance"] = round(resistance, 2)
        result["support"] = round(support, 2)

        # Distance to support/resistance as % of price
        if result["price"] > 0:
            result["dist_to_resistance"] = round((resistance - result["price"]) / result["price"] * 100, 2)
            result["dist_to_support"] = round((result["price"] - support) / result["price"] * 100, 2)

    # ===== Trend Classification =====
    if result["ema_50"] and result["ema_200"]:
        if result["price"] > result["ema_50"] > result["ema_200"]:
            result["trend"] = "Bullish"
        elif result["price"] < result["ema_50"] < result["ema_200"]:
            result["trend"] = "Bearish"
        else:
            result["trend"] = "Sideways / Mixed"
    else:
        result["trend"] = "Not enough data"

    # RSI interpretation
    if result["rsi_14"]:
        if result["rsi_14"] > 70:
            result["rsi_signal"] = "Overbought"
        elif result["rsi_14"] < 30:
            result["rsi_signal"] = "Oversold"
        elif result["rsi_14"] > 55:
            result["rsi_signal"] = "Bullish bias"
        elif result["rsi_14"] < 45:
            result["rsi_signal"] = "Bearish bias"
        else:
            result["rsi_signal"] = "Neutral"

    # MACD signal
    if result["macd"] is not None and result["macd_signal"] is not None:
        if result["macd"] > result["macd_signal"]:
            result["macd_signal_text"] = "Bullish (above signal line)"
        else:
            result["macd_signal_text"] = "Bearish (below signal line)"

    # ATR-based volatility for position sizing (Druckenmiller style)
    if result["atr_14"] and result["price"]:
        result["atr_pct"] = round((result["atr_14"] / result["price"]) * 100, 2)
        if result["atr_pct"] > 5:
            result["volatility"] = "High"
        elif result["atr_pct"] > 2:
            result["volatility"] = "Moderate"
        else:
            result["volatility"] = "Low"

    # ===== Druckenmiller Position Sizing Helper =====
    # Based on ATR: risk 1% of capital per trade, stop = 1.5x ATR
    # This tells you how many units to buy for a given account size
    if result["atr_14"] and result["price"]:
        stop_distance = result["atr_14"] * 1.5  # 1.5x ATR stop
        # Example: $1000 account, 1% risk = $10 risk budget
        risk_per_unit = stop_distance
        # Max units at 1% risk on $1000 = $10 / risk_per_unit
        result["position_size_guide"] = {
            "stop_distance": round(stop_distance, 2),
            "max_units_1pct_risk_1000acct": round(10 / risk_per_unit, 4) if risk_per_unit > 0 else None,
            "max_units_2pct_risk_1000acct": round(20 / risk_per_unit, 4) if risk_per_unit > 0 else None,
        }

    return result


def get_multi_analysis(symbols: list) -> dict:
    """Run technical analysis on multiple symbols at once."""
    results = {}
    for sym in symbols:
        try:
            results[sym] = get_technical_analysis(sym)
        except Exception as e:
            results[sym] = {"error": str(e)}
    return results


def format_analysis(result: dict) -> str:
    """Format the full analysis for display — Druckenmiller trading dashboard style."""
    if "error" in result:
        return f"ERROR: {result['error']}"

    lines = []
    lines.append(f"{result['symbol']} — ${result['price']}")
    lines.append(f"   Trend: {result['trend']}")

    if result.get("rsi_14"):
        lines.append(f"   RSI(14): {result['rsi_14']} — {result.get('rsi_signal', '')}")

    if result.get("macd") is not None:
        lines.append(f"   MACD: {result['macd']} (signal: {result['macd_signal']}) — {result.get('macd_signal_text', '')}")

    lines.append(f"   EMA: 50={result.get('ema_50','N/A')} | 100={result.get('ema_100','N/A')} | 200={result.get('ema_200','N/A')}")
    lines.append(f"   SMA(20): {result.get('sma_20', 'N/A')}")

    if result.get("bb_upper"):
        lines.append(f"   Bollinger: Upper={result['bb_upper']} Mid={result['bb_mid']} Lower={result['bb_lower']} Width={result.get('bb_width','N/A')}")
        lines.append(f"   BB Position: {result.get('bb_position','N/A')} (0=lower band, 1=upper band)")

    if result.get("squeeze_status"):
        lines.append(f"   Squeeze: {result['squeeze_status']} (ratio: {result.get('squeeze_ratio','N/A')}, narrowing {result.get('squeeze_days',0)} days)")

    if result.get("stoch_k"):
        lines.append(f"   Stochastic: K={result['stoch_k']} D={result['stoch_d']} — {result.get('stoch_signal', '')}")

    if result.get("adx_14"):
        lines.append(f"   ADX(14): {result['adx_14']} — {result.get('adx_signal', '')}")

    if result.get("obv"):
        lines.append(f"   OBV: {result['obv']} — {result.get('obv_signal', '')}")

    if result.get("volume_ratio"):
        lines.append(f"   Volume: {result['volume_ratio']}x avg — {result.get('volume_signal', '')}")

    if result.get("atr_14"):
        lines.append(f"   ATR(14): {result['atr_14']} ({result.get('atr_pct',0)}% — {result.get('volatility','')} volatility)")

    if result.get("fib_direction"):
        lines.append(f"   Fibonacci ({result['fib_direction']}): Swing ${result['fib_swing_low']} -> ${result['fib_swing_high']}")
        lines.append(f"     23.6%=${result.get('fib_236','N/A')} | 38.2%=${result.get('fib_382','N/A')} | 50%=${result.get('fib_500','N/A')}")
        lines.append(f"     61.8%=${result.get('fib_618','N/A')} | 78.6%=${result.get('fib_786','N/A')}")
        lines.append(f"     Nearest: {result.get('fib_nearest','N/A')}")

    if result.get("resistance"):
        lines.append(f"   Support: ${result['support']} ({result.get('dist_to_support',0)}% below)")
        lines.append(f"   Resistance: ${result['resistance']} ({result.get('dist_to_resistance',0)}% above)")

    if result.get("position_size_guide"):
        ps = result["position_size_guide"]
        lines.append(f"   Position Sizing: Stop={ps['stop_distance']} | Max units @1% risk on $1K={ps['max_units_1pct_risk_1000acct']} | @2%={ps['max_units_2pct_risk_1000acct']}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Full test on current portfolio + watchlist
    test_symbols = [
        "BZ=F",          # Brent Oil (biggest position — 14 units)
        "GC=F",          # Gold futures (second biggest — 0.30 oz)
        "^GSPC",         # S&P 500 (short hedge — 0.03 units)
        "BTC-USD",       # Bitcoin (just closed — monitoring)
        "NVDA",          # Watchlist
        "DX-Y.NYB",      # DXY Dollar Index (macro key)
    ]

    print("=" * 70)
    print("BIG BRAIN APE — FULL TECHNICAL ANALYSIS DASHBOARD")
    print("Druckenmiller Macro Agent | 98-Asset Universe")
    print("=" * 70)

    for sym in test_symbols:
        result = get_technical_analysis(sym)
        print()
        print(format_analysis(result))
        print("-" * 70)
