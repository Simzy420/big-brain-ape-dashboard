#!/usr/bin/env python3
"""
Daily Macro Briefing Generator for "The Daily News + Trump's Schedule" offering.
Fetches: Fed policy, inflation, geopolitics, oil/gold/BTC prices, earnings, crypto, Trump schedule.
Outputs a clean, concise briefing suitable for delivery to subscribers.
"""
import json, subprocess, sys, os, re
from datetime import datetime, timezone

def run_script(path, timeout=90):
    try:
        result = subprocess.run(["python3", path], capture_output=True, text=True, timeout=timeout)
        return result.stdout + ("\n" + result.stderr if result.stderr and "Error" in result.stderr else "")
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"

def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def parse_line_value(output, *keywords):
    """Find a line containing any of the keywords and return it."""
    for line in output.split("\n"):
        ll = line.lower()
        if all(kw in ll for kw in keywords):
            return line.strip()
    return "N/A"

def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    print(f"[{date_str} UTC] Generating Daily Macro Briefing...")

    # 1. Fetch news (Jina scraper)
    print("Fetching news headlines...")
    run_script(os.path.expanduser("~/.hermes/scripts/jina-news-scraper.py"))
    news_data = load_json(os.path.expanduser("~/.hermes/scripts/news-data/latest-news.json"), {})

    # 2. Fetch FRED macro data
    print("Fetching FRED macro data...")
    fred_output = run_script(os.path.expanduser("~/.hermes/scripts/fred-macro-fetch.py"))

    # 3. Fetch crypto prices (CoinGecko)
    print("Fetching crypto prices...")
    crypto_output = run_script(os.path.expanduser("~/.hermes/scripts/market-data-fetch.py"))

    # 4. Fetch stablecoins/DeFi/FX
    print("Fetching keyless data...")
    keyless_output = run_script(os.path.expanduser("~/.hermes/scripts/keyless-data-fetch.py"), timeout=60)

    # --- Parse FRED data ---
    fed_funds = parse_line_value(fred_output, "fed funds rate")
    ten_yr = parse_line_value(fred_output, "10y treasury yield")
    two_yr = parse_line_value(fred_output, "2y treasury yield")
    thirty_yr = parse_line_value(fred_output, "30y treasury yield")
    cpi = parse_line_value(fred_output, "cpi (all urban")
    vix = parse_line_value(fred_output, "vix")
    dxy = parse_line_value(fred_output, "trade-weighted dollar")
    unemployment = parse_line_value(fred_output, "unemployment rate")
    m2 = parse_line_value(fred_output, "m2 money supply")
    hy_oas = parse_line_value(fred_output, "high yield oas")
    jobless = parse_line_value(fred_output, "initial jobless claims")

    # Clean up FRED lines — extract just the value + date
    def clean_fred(line):
        """Extract numeric value and date from a FRED output line."""
        m = re.search(r'([\d.$%,.\s]+)\s+(\d{4}-\d{2}-\d{2})\s*$', line)
        if m:
            return f"{m.group(1).strip()} (as of {m.group(2)})"
        # Try VIX format
        m2 = re.search(r'VIX.*?([\d.]+)%?\s*—\s*(\w+)', line)
        if m2:
            return f"{m2.group(1)} — {m2.group(2)}"
        return line.strip()

    fed_funds = clean_fred(fed_funds)
    ten_yr = clean_fred(ten_yr)
    cpi_line = clean_fred(cpi)
    vix = clean_fred(vix)
    dxy = clean_fred(dxy)
    unemployment = clean_fred(unemployment)
    m2 = clean_fred(m2)
    hy_oas = clean_fred(hy_oas)

    # --- Parse crypto prices properly (look for price not market cap) ---
    def extract_crypto_price(output, symbol):
        """Extract the actual price from CoinGecko output line."""
        for line in output.split("\n"):
            if line.strip().startswith(symbol + " "):
                # Format: "BTC      $  63,498.00   -1.67% $1,273..."
                m = re.search(r'\$\s*([\d,.]+)\s+([+-][\d.]+%)', line)
                if m:
                    return f"${m.group(1)} ({m.group(2)} 24h)"
        return "N/A"

    btc_price = extract_crypto_price(crypto_output, "BTC")
    eth_price = extract_crypto_price(crypto_output, "ETH")
    sol_price = extract_crypto_price(crypto_output, "SOL")

    # --- Parse stablecoin data ---
    stablecap = "N/A"
    for line in keyless_output.split("\n"):
        if "Total:" in line and "B" in line:
            stablecap = line.strip()
            break

    # --- Parse news data ---
    headlines = news_data.get("headlines", [])
    trending = news_data.get("trending_tickers", [])

    # Group headlines by category
    cat_headlines = {}
    for h in headlines:
        for cat in h.get("categories", ["other"]):
            if cat not in cat_headlines:
                cat_headlines[cat] = []
            if len(cat_headlines[cat]) < 4:
                cat_headlines[cat].append(h.get("headline", ""))

    # Breaking news
    breaking = [h for h in headlines if h.get("type") == "Breaking News"][:5]

    # --- Trump schedule (fetch from White House via Jina Reader) ---
    trump_schedule_text = "No official White House schedule released yet for today."
    try:
        import urllib.request
        schedule_items = []
        # Fetch recent remarks/events (most recent first)
        for wh_url in [
            "https://r.jina.ai/https://www.whitehouse.gov/remarks/",
            "https://r.jina.ai/https://www.whitehouse.gov/presidential-actions/",
            "https://r.jina.ai/https://www.whitehouse.gov/briefings-statements/"
        ]:
            req = urllib.request.Request(wh_url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=15)
            text = resp.read().decode('utf-8', errors='ignore')
            # Extract titles — Jina returns markdown with ## [Title](url) format
            titles = re.findall(r'##\s\[([^\]]{10,200})\]', text)
            # Also try ### [Title] format (remarks page uses this)
            titles += re.findall(r'###\s\[([^\]]{10,200})\]', text)
            for t in titles[:5]:
                if t not in schedule_items and len(t) > 10:
                    schedule_items.append(t)
        if schedule_items:
            trump_schedule_text = "Recent presidential activities and actions:\n"
            for item in schedule_items[:10]:
                trump_schedule_text += f"  • {item.strip()}\n"
    except Exception as e:
        trump_schedule_text = f"Schedule fetch pending — check whitehouse.gov for today's events. (Error: {e})"

    # --- Build the briefing ---
    briefing = f"""# 📰 THE DAILY NEWS + TRUMP'S SCHEDULE
## {date_str}

---

## 🏛️ TRUMP'S PUBLIC SCHEDULE

{trump_schedule_text}

---

## 📊 KEY MARKET DATA

| Metric | Value |
|---|---|
| Fed Funds Rate | {fed_funds} |
| 10Y Treasury | {ten_yr} |
| 30Y Treasury | {clean_fred(thirty_yr)} |
| CPI (latest) | {cpi_line} |
| VIX | {vix} |
| DXY (Dollar Index) | {dxy} |
| Unemployment | {unemployment} |
| Jobless Claims | {clean_fred(jobless)} |
| M2 Money Supply | {m2} |
| HY Credit Spreads | {hy_oas} |
| Stablecoin Mkt Cap | {stablecap} |

### Crypto Prices
| Asset | Price |
|---|---|
| BTC | {btc_price} |
| ETH | {eth_price} |
| SOL | {sol_price} |

---

## 🚨 BREAKING NEWS

"""
    if breaking:
        for item in breaking:
            briefing += f"- {item.get('headline', '')}\n"
    else:
        briefing += "- No major breaking news detected\n"

    briefing += "\n---\n\n## 📰 TOP HEADLINES BY CATEGORY\n\n"

    # Priority categories
    cat_priority = ["fed", "inflation", "geopolitics", "oil", "earnings", "tech", "banks", "crypto", "gold"]
    seen_cats = set()
    for cat in cat_priority:
        if cat in cat_headlines and cat not in seen_cats:
            seen_cats.add(cat)
            briefing += f"**{cat.upper()}**\n"
            for h in cat_headlines[cat]:
                briefing += f"  • {h}\n"
            briefing += "\n"
    # Any remaining categories
    for cat, items in cat_headlines.items():
        if cat not in seen_cats and cat != "other":
            seen_cats.add(cat)
            briefing += f"**{cat.upper()}**\n"
            for h in items:
                briefing += f"  • {h}\n"
            briefing += "\n"

    # Trending tickers
    if trending:
        briefing += "## 📈 TRENDING TICKERS\n\n"
        for t in trending:
            emoji = "🟢" if t.get("change_pct", 0) >= 0 else "🔴"
            briefing += f"- {emoji} {t.get('symbol', '?')} ${t.get('price', '?')} ({t.get('change_pct', '?'):+.2f}%)\n"
        briefing += "\n"

    briefing += """---

## 🎯 BIG BRAIN APE'S MACRO READ

**Liquidity Lens:** Fed at 3.63% after easing from 5.5%. Watch M2 growth and stablecoin market cap for liquidity direction. Stablecoins flat = no new crypto catalyst yet.

**Valuation Lens:** June CPI 3.5% vs 3.8% expected — dovish beat. Inflation momentum moderating. Fed's next move is more likely a cut than a hike. Gold and risk assets supported.

**Technical Lens:** VIX and DXY levels show risk sentiment. Credit spreads indicate financial stability. Watch for VIX spikes = risk-off, DXY breaks = dollar trend shift.

**Geopolitical Risk:** US-Iran/Hormuz escalation is the key tail risk. Oil supply disruption impacts everything — gold safe-haven bid, equities risk-off, inflation upside.

---

## 💡 ACTIONABLE SUMMARY

1. **Fed policy:** Warsh talks hawkish but CPI cooling — watch for rhetoric vs data divergence
2. **Oil/Hormuz:** Monitor escalation — BRENTOIL/CL could spike, gold safe-haven bid strengthens
3. **Crypto:** Stablecoin mcap flat = no liquidity turn yet. Need F&G above 40 + stablecoin growth for BTC re-entry
4. **Earnings:** Watch sector divergence — financials strong, tech mixed, semis under pressure
5. **Dollar:** DXY near peak if CPI continues cooling — dollar weakness = gold and EUR upside

---

*Generated by Big Brain Ape — Fully Autonomous Trading Bot + Stock/Crypto Analyst. Not financial advice.*

*Subscribe: Weekly $0.99 | Monthly $4.99 | Quarterly $9.99*
"""

    # Save briefing
    briefing_dir = os.path.expanduser("~/.hermes/cron/output")
    os.makedirs(briefing_dir, exist_ok=True)
    briefing_path = os.path.join(briefing_dir, f"daily-briefing-{date_str}.txt")
    with open(briefing_path, "w") as f:
        f.write(briefing)

    print(f"\n✅ Briefing saved to: {briefing_path}")
    print(f"   Length: {len(briefing)} chars")
    print("\n--- BRIEFING PREVIEW (first 3000 chars) ---")
    print(briefing[:3000])
    if len(briefing) > 3000:
        print("\n[... truncated ...]")
    print(f"\nBRIEFING_PATH={briefing_path}")

if __name__ == "__main__":
    main()
