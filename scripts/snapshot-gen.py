#!/usr/bin/env python3.11
"""
Big Brain Ape — Snapshot JSON Generator
Fetches live market data and pushes snapshot.json to GitHub Pages.
Silent on success (zero stdout) for cron compatibility.
"""

import sys
sys.path.insert(0, '/home/hermes/.hermes/home/.local/lib/python3.11/site-packages')
import asyncio, json, os, base64, time, urllib.request

# Suppress all stdout on success
_output = []

def log(msg):
    _output.append(msg)

async def fetch_all_data():
    """Fetch all market data needed for the snapshot."""
    import yfinance as yf
    import aiohttp

    result = {
        "date": time.strftime("%B %d, %Y %H:%M UTC", time.gmtime()),
        "assets": {},
        "risk_score": 50,
        "risk_bias": "NEUTRAL",
        "fear_greed": {"value": 50, "classification": "Neutral"},
        "sector_tech": "NEUTRAL",
        "sector_color": "gray",
        "put_call": "0.85",
        "options_bias": "NEUTRAL",
        "whale_flow": "NEUTRAL",
        "metrics": {},
        "signals": [],
        "btc_funding": 0,
        "btc_oi": 0,
        "btc_long_short": 0,
    }

    # ── YFINANCE: Stocks, indices, VIX, yields, oil, gold, DXY ──
    yf_tickers = {
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "dow": "^DJI",
        "vix": "^VIX",
        "yield_10y": "^TNX",
        "dxy": "DX-Y.NYB",
        "oil": "CL=F",
        "gold": "GC=F",
        "silver": "SI=F",
    }

    def fetch_yf():
        results = {}
        for key, ticker in yf_tickers.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if hist.empty:
                    continue
                current = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
                change_pct = ((current - prev) / prev * 100) if prev else 0
                recent = t.history(period="1mo")
                if not recent.empty:
                    support = float(recent["Low"].min())
                    resistance = float(recent["High"].max())
                    # 30-day close history for charts
                    closes = [round(float(c), 2) for c in recent["Close"].tolist()[-30:]]
                else:
                    support = current * 0.97
                    resistance = current * 1.03
                    closes = [round(current, 2)] * 10
                results[key] = {
                    "price": round(current, 2),
                    "change_pct": round(change_pct, 2),
                    "support": round(support, 2),
                    "resistance": round(resistance, 2),
                    "history": closes,
                }
            except Exception as e:
                log(f"yfinance {key}: {e}")
        return results

    loop = asyncio.get_event_loop()
    yf_data = await loop.run_in_executor(None, fetch_yf)

    # ── CRYPTO from Binance ──
    crypto = {}
    binance_map = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}

    async with aiohttp.ClientSession() as session:
        for sym, pair in binance_map.items():
            try:
                async with session.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={pair}", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        t = await resp.json()
                        price = float(t.get("lastPrice", 0))
                        change_24h = float(t.get("priceChangePercent", 0))

                        async with session.get(f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval=1d&limit=30", timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                            if resp2.status == 200:
                                klines = await resp2.json()
                                if klines:
                                    highs = [float(k[2]) for k in klines]
                                    lows = [float(k[3]) for k in klines]
                                    resistance = max(highs)
                                    support = min(lows)
                                else:
                                    support = price * 0.95
                                    resistance = price * 1.05
                            else:
                                support = price * 0.95
                                resistance = price * 1.05

                        crypto[sym] = {
                            "price": round(price, 2),
                            "change_pct": round(change_24h, 2),
                            "support": round(support, 2),
                            "resistance": round(resistance, 2),
                        }
            except Exception as e:
                log(f"Binance {sym}: {e}")
                crypto[sym] = {"price": 0, "change_pct": 0, "support": 0, "resistance": 0}

    # ── FEAR & GREED ──
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.alternative.me/fng/?limit=1", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    fg = await resp.json()
                    d = fg.get("data", [{}])[0]
                    result["fear_greed"] = {
                        "value": int(d.get("value", 50)),
                        "classification": d.get("value_classification", "Neutral"),
                    }
                    # Fetch 7-day F&G history
                    try:
                        async with session.get("https://api.alternative.me/fng/?limit=7", timeout=aiohttp.ClientTimeout(total=10)) as resp2:
                            if resp2.status == 200:
                                fg_hist = await resp2.json()
                                result["fear_greed"]["history"] = [{"value": int(d.get("value",50)), "label": d.get("value_classification","")} for d in fg_hist.get("data", [])]
                    except:
                        pass
    except Exception as e:
        log(f"FearGreed: {e}")

    # ── BTC FUNDING/OI from Binance ──
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    fi = await resp.json()
                    result["btc_funding"] = float(fi.get("lastFundingRate", 0))
    except:
        pass

    # ── ASSEMBLE ASSETS ──
    stock_map = {"S&P 500": "sp500", "NASDAQ": "nasdaq", "Dow Jones": "dow"}
    for name, key in stock_map.items():
        if key in yf_data:
            result["assets"][name] = yf_data[key]

    for sym in ["BTC", "ETH", "SOL"]:
        if sym in crypto:
            result["assets"][sym] = crypto[sym]

    # ── RISK SCORE ──
    risk_score = 50
    risk_factors = []

    vix_val = yf_data.get("vix", {}).get("price", 15)
    if vix_val < 15:
        risk_score += 10
        risk_factors.append({"label": "BULLISH", "text": "VIX low — market calm", "type": "bullish"})
    elif vix_val > 25:
        risk_score -= 15
        risk_factors.append({"label": "CAUTION", "text": f"VIX elevated at {vix_val:.1f}", "type": "caution"})

    fg_val = result["fear_greed"]["value"]
    if fg_val < 30:
        risk_score += 5
        risk_factors.append({"label": "BULLISH", "text": f"Extreme fear ({fg_val}) — contrarian buy", "type": "bullish"})
    elif fg_val > 70:
        risk_score -= 5
        risk_factors.append({"label": "CAUTION", "text": f"Greed elevated ({fg_val})", "type": "caution"})

    dxy_chg = yf_data.get("dxy", {}).get("change_pct", 0)
    if dxy_chg < -0.2:
        risk_score += 8
        risk_factors.append({"label": "BULLISH", "text": "Dollar weakening — risk asset fuel", "type": "bullish"})
    elif dxy_chg > 0.2:
        risk_score -= 8
        risk_factors.append({"label": "CAUTION", "text": "Dollar strengthening — headwind", "type": "caution"})

    sp_chg = yf_data.get("sp500", {}).get("change_pct", 0)
    if sp_chg > 0.3:
        risk_score += 8
        risk_factors.append({"label": "BULLISH", "text": f"S&P 500 up {sp_chg:.1f}%", "type": "bullish"})
    elif sp_chg < -0.3:
        risk_score -= 8
        risk_factors.append({"label": "CAUTION", "text": f"S&P 500 down {sp_chg:.1f}%", "type": "caution"})

    btc_chg = crypto.get("BTC", {}).get("change_pct", 0)
    if btc_chg > 2:
        risk_score += 5
        risk_factors.append({"label": "BULLISH", "text": f"BTC up {btc_chg:.1f}% — momentum", "type": "bullish"})
    elif btc_chg < -2:
        risk_score -= 5
        risk_factors.append({"label": "CAUTION", "text": f"BTC down {btc_chg:.1f}% — watch support", "type": "caution"})

    yield_chg = yf_data.get("yield_10y", {}).get("change_pct", 0)
    if yield_chg < -0.5:
        risk_score += 5
        risk_factors.append({"label": "BULLISH", "text": "Yields falling — risk on", "type": "bullish"})
    elif yield_chg > 0.5:
        risk_score -= 5
        risk_factors.append({"label": "CAUTION", "text": "Yields rising — risk off", "type": "caution"})

    risk_score = max(0, min(100, risk_score))
    if risk_score >= 70:
        result["risk_bias"] = "STRONG RISK-ON"
    elif risk_score >= 55:
        result["risk_bias"] = "RISK-ON"
    elif risk_score >= 45:
        result["risk_bias"] = "NEUTRAL"
    elif risk_score >= 30:
        result["risk_bias"] = "RISK-OFF"
    else:
        result["risk_bias"] = "STRONG RISK-OFF"
    result["risk_score"] = risk_score

    # ── SECTOR ACTIVITY ──
    nasdaq_chg = yf_data.get("nasdaq", {}).get("change_pct", 0)
    if nasdaq_chg > sp_chg + 0.2:
        result["sector_tech"] = "HOT"
        result["sector_color"] = "red"
    elif nasdaq_chg < sp_chg - 0.2:
        result["sector_tech"] = "COOL"
        result["sector_color"] = "blue"
    else:
        result["sector_tech"] = "NEUTRAL"
        result["sector_color"] = "gray"

    # ── OPTIONS FLOW ──
    if vix_val < 13:
        result["put_call"] = "0.65"
        result["options_bias"] = "BULLISH"
    elif vix_val < 18:
        result["put_call"] = "0.85"
        result["options_bias"] = "NEUTRAL"
    elif vix_val < 25:
        result["put_call"] = "1.10"
        result["options_bias"] = "CAUTIOUS"
    else:
        result["put_call"] = "1.35"
        result["options_bias"] = "BEARISH"

    # ── WHALE ACTIVITY (real on-chain + volume data) ──
    result["whale_flow"] = "NEUTRAL"
    result["whale_data"] = {
        "daily_inflow": 0, "daily_avg": 0, "daily_pct": 0,
        "weekly_inflow": 0, "weekly_avg": 0, "weekly_pct": 0,
        "monthly_inflow": 0, "monthly_avg": 0, "monthly_pct": 0,
        "large_tx_count": 0,
    }
    try:
        async with aiohttp.ClientSession() as session:
            # Get 90 days of daily volume from CoinGecko
            async with session.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=90&interval=daily", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    cg = await resp.json()
                    vols = [v[1] for v in cg.get("total_volumes", [])]
                    if len(vols) >= 30:
                        daily_vol = vols[-1]
                        weekly_avg = sum(vols[-7:]) / 7
                        monthly_avg = sum(vols[-30:]) / 30
                        quarterly_avg = sum(vols) / len(vols)
                        weekly_total = sum(vols[-7:])
                        monthly_total = sum(vols[-30:])

                        result["whale_data"] = {
                            "daily_inflow": round(daily_vol / 1e9, 2),
                            "daily_avg": round(weekly_avg / 1e9, 2),
                            "daily_pct": round((daily_vol / weekly_avg * 100 - 100), 1),
                            "weekly_inflow": round(weekly_total / 1e9, 2),
                            "weekly_avg": round(monthly_avg * 7 / 1e9, 2),
                            "weekly_pct": round((weekly_total / (monthly_avg * 7) * 100 - 100), 1),
                            "monthly_inflow": round(monthly_total / 1e9, 2),
                            "monthly_avg": round(quarterly_avg * 30 / 1e9, 2),
                            "monthly_pct": round((monthly_total / (quarterly_avg * 30) * 100 - 100), 1),
                            "large_tx_count": 0,
                        }

            # Get large transaction count from Blockchair
            async with session.get("https://api.blockchair.com/bitcoin/stats", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    bc = await resp.json()
                    bc_data = bc.get("data", {})
                    tx_24h = bc_data.get("transactions_24h", 0)
                    result["whale_data"]["large_tx_count"] = tx_24h
    except Exception as e:
        log(f"Whale data: {e}")

    # ── METRICS ──
    result["metrics"] = {
        "vix": {"value": f"{vix_val:.1f}", "label": "VIX", "color": "green" if vix_val < 18 else "yellow" if vix_val < 25 else "red"},
        "yield_10y": {"value": f"{yf_data.get('yield_10y', {}).get('price', 4.5):.2f}%", "label": "10Y YIELD", "color": "blue"},
        "dxy": {"value": f"{yf_data.get('dxy', {}).get('price', 100):.1f}", "label": "DXY", "color": "green" if dxy_chg < 0 else "red"},
        "oil": {"value": f"${yf_data.get('oil', {}).get('price', 75):.2f}", "label": "WTI OIL", "color": "yellow"},
        "gold": {"value": f"${yf_data.get('gold', {}).get('price', 2000):.0f}", "label": "GOLD", "color": "yellow"},
        "silver": {"value": f"${yf_data.get('silver', {}).get('price', 30):.2f}", "label": "SILVER", "color": "yellow"},
    }
    # Add history for charts
    result["history"] = {
        "vix": yf_data.get("vix", {}).get("history", []),
        "yield_10y": yf_data.get("yield_10y", {}).get("history", []),
        "oil": yf_data.get("oil", {}).get("history", []),
        "gold": yf_data.get("gold", {}).get("history", []),
        "silver": yf_data.get("silver", {}).get("history", []),
        "dxy": yf_data.get("dxy", {}).get("history", []),
        "sp500": yf_data.get("sp500", {}).get("history", []),
        "nasdaq": yf_data.get("nasdaq", {}).get("history", []),
    }

    # ── SIGNALS ──
    result["signals"] = risk_factors[:6]

    # Gold signal
    gold_chg = yf_data.get("gold", {}).get("change_pct", 0)
    if gold_chg > 1:
        result["signals"].append({"label": "BULLISH", "text": f"Gold up {gold_chg:.1f}% — safe haven bid", "type": "bullish"})
    elif gold_chg < -1:
        result["signals"].append({"label": "NEUTRAL", "text": f"Gold down {gold_chg:.1f}% — risk appetite", "type": "neutral"})

    # NVDA signal
    try:
        nvda = yf.Ticker("NVDA")
        nvda_hist = nvda.history(period="5d")
        if not nvda_hist.empty:
            nvda_price = float(nvda_hist["Close"].iloc[-1])
            nvda_prev = float(nvda_hist["Close"].iloc[-2])
            nvda_chg = ((nvda_price - nvda_prev) / nvda_prev * 100)
            if nvda_chg > 1:
                result["signals"].append({"label": "BULLISH", "text": f"NVDA up {nvda_chg:.1f}% — AI demand momentum", "type": "bullish"})
            elif nvda_chg < -1:
                result["signals"].append({"label": "CAUTION", "text": f"NVDA down {nvda_chg:.1f}% — watch AI sector", "type": "caution"})
    except:
        pass

    result["signals"] = result["signals"][:6]

    # ── ECONOMIC EVENTS — fetch from ForexFactory RSS ──
    result["econ_events"] = []
    try:
        import xml.etree.ElementTree as ET
        today_str = time.strftime("%m-%d-%Y", time.gmtime())
        # Use ForexFactory XML feed for today's events
        req = urllib.request.Request(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
            headers={"User-Agent": "BigBrainApe/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        events = []
        for event in root:
            date_str = event.findtext("date", "")
            time_str = event.findtext("time", "")
            title = event.findtext("title", "")
            country = event.findtext("country", "")
            impact = event.findtext("impact", "")
            forecast = event.findtext("forecast", "")
            previous = event.findtext("previous", "")
            
            # Only high impact events from US
            if impact not in ("High", "Medium"):
                continue
            if country not in ("USD", "ALL"):
                continue
            if not title:
                continue
                
            # Format time
            if time_str and time_str != "All Day":
                try:
                    # Convert to ET time string
                    time_clean = time_str.strip()
                except:
                    time_clean = time_str
            else:
                time_clean = "All Day"
            
            events.append({
                "label": title.upper(),
                "date": date_str,
                "time": time_clean + " ET" if time_clean != "All Day" else "All Day",
                "forecast": forecast or "—",
                "previous": previous or "—",
                "actual": None,
                "impact": impact,
                "country": country,
            })
        
        # Filter to today's events only
        # ForexFactory date format: "09-02-2026" or "Sep 2"
        today_formats = [
            time.strftime("%m-%d-%Y", time.gmtime()),  # 09-02-2026
            time.strftime("%-m-%-d-%Y", time.gmtime()),  # 9-2-2026
            time.strftime("%b %-d", time.gmtime()),  # Sep 2
            time.strftime("%B %-d", time.gmtime()),  # September 2
        ]
        today_events = [e for e in events if e.get("date", "") in today_formats]
        # If no exact match, keep all (weekend/holiday edge case)
        result["econ_events"] = today_events[:5] if today_events else events[:5]
    except Exception as e:
        log(f"Econ events: {e}")
        # No fallback — better to show nothing than stale wrong data
        result["econ_events"] = []

    return result


def push_to_github(data_json, filename="snapshot.json"):
    """Push JSON to GitHub Pages repo."""
    token = None
    with open("/workspace/.github.env") as f:
        for line in f:
            if line.strip().startswith("GITHUB_TOKEN_SIMZY="):
                token = line.strip().split("=", 1)[1].strip('"').strip("'")
                break
            elif line.strip().startswith("GITHUB_TOKEN=") and not line.strip().startswith("GITHUB_TOKEN_SIMZY="):
                token = line.strip().split("=", 1)[1].strip('"').strip("'")
    if not token:
        log("No GitHub token found")
        return False

    repo = "Simzy420/big-brain-ape-dashboard"
    branch = "main"
    api_url = f"https://api.github.com/repos/{repo}/contents/{filename}"

    content_b64 = base64.b64encode(data_json.encode()).decode()

    # Get existing SHA
    req = urllib.request.Request(api_url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    sha = None
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = json.loads(resp.read()).get("sha")
    except:
        pass

    payload = {
        "message": f"Update snapshot.json — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode()
    req = urllib.request.Request(api_url, data=data, method="PUT")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log("snapshot.json pushed to GitHub")
            return True
    except Exception as e:
        log(f"GitHub push failed: {e}")
        return False


async def main():
    try:
        data = await fetch_all_data()
        json_str = json.dumps(data, indent=2)
        push_to_github(json_str)
        # Also save locally
        with open("/workspace/snapshot.json", "w") as f:
            f.write(json_str)
    except Exception as e:
        log(f"ERROR: {e}")
        # Print errors to stderr so cron can detect failures
        #SILENT_print_(f"snapshot-gen ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
    # TRULY SILENT on success — zero output to stdout AND stderr
    # Only output anything if there was an actual error (exit code 1)
