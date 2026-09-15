#!/usr/bin/env python3.11
"""
Big Brain Ape — Individual Analyst Ratings Fetcher
Fetches individual analyst firm ratings (Goldman Sachs, JP Morgan, etc.) with
specific price targets from stockanalysis.com and pushes to GitHub Pages as
analyst-ratings.json.

Silent on success (zero stdout) for cron compatibility.
"""

import json, os, sys, base64, time, urllib.request, re, html as html_mod

# Suppress stdout on success
_output = []

def log(msg):
    _output.append(msg)

# Popular tickers to pre-fetch ratings for
TICKERS = [
    "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "META", "AMZN", "AMD",
    "NFLX", "PLTR", "COIN", "HOOD", "MSTR", "SPY", "QQQ", "DIA",
    "BABA", "GME", "AMC", "SOFI", "RIVN", "INTC", "MU", "ARM",
    "SMCI", "AVGO", "SHOP", "SQ", "ROKU", "SNAP", "PYPL", "UBER",
    "ABNB", "DKNG", "DKNG", "LLY", "COST", "JPM", "V", "MA",
    "DIS", "NKE", "CRM", "ORCL", "ADBE", "PINS", "ZM", "DOCU",
    "CRWD", "PANW", "FTNT", "NET", "DDOG", "SNOW", "MDB", "TEAM",
    "OKTA", "ZS", "S", "PATH", "AI", "U", "RBLX", "CHWY",
    "ETSY", "W", "PLUG", "FCEL", "BLNK", "NIO", "XPEV", "LI",
    "PDD", "JD", "BIDU", "TSM", "ASML", "QCOM", "NVAX", "MRNA",
    "BNTX", "JNJ", "PFE", "MRK", "ABT", "TMO", "UNH", "CVX",
    "XOM", "BP", "SHEL", "COP", "EOG", "PSX", "VLO", "MPC",
    "FCX", "NEM", "GOLD", "AA", "CENX", "CLF", "STLD", "NUE",
    "WMT", "TGT", "COST", "HD", "LOW", "DG", "FIVE", "BBBY",
    "SBUX", "MCD", "CMG", "DPZ", "YUM", "WEN", "JACK", "FAT",
    "AAP", "AZO", "ORLY", "MNRO", "FAST", "POOL", "HD", "LOW",
]

# Remove duplicates while preserving order
TICKERS = list(dict.fromkeys(TICKERS))

def fetch_analyst_ratings(symbol):
    """Fetch individual analyst firm ratings from stockanalysis.com"""
    # Handle ETFs (SPY, QQQ, DIA) — stockanalysis uses /etf/ path for ETFs
    etfs = {"SPY", "QQQ", "DIA", "IWM", "XLF", "XLE", "XLK", "XLV", "XLY", "XLP", "XLI", "XLB", "XLRE", "XLU", "XLC"}
    if symbol in etfs:
        url = f"https://stockanalysis.com/etf/{symbol.lower()}/holdings/"
    else:
        url = f"https://stockanalysis.com/stocks/{symbol.lower()}/forecast/"
    
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None
    
    # Decode HTML entities
    raw = html_mod.unescape(raw)
    
    # Parse all tables
    tables = re.findall(r'<table[^>]*>(.*?)</table>', raw, re.DOTALL)
    
    result = {
        "symbol": symbol,
        "priceTargets": {"low": None, "average": None, "median": None, "high": None},
        "analysts": [],
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    }
    
    for table_html in tables:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        if not rows:
            continue
        
        header_cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', rows[0], re.DOTALL)
        header_clean = [re.sub(r'<[^>]+>', '', c).strip() for c in header_cells]
        header_text = ' '.join(header_clean)
        
        # Price targets table
        if 'Low' in header_clean and 'Average' in header_clean and 'High' in header_clean:
            for row in rows[1:]:
                cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
                clean = [re.sub(r'<[^>]+>', '', c).strip().replace('$', '').replace(',', '') for c in cells]
                if len(clean) >= 5 and 'Price' in clean[0]:
                    result["priceTargets"] = {
                        "low": clean[1],
                        "average": clean[2],
                        "median": clean[3],
                        "high": clean[4]
                    }
        
        # Individual analyst ratings table
        if 'Analyst' in header_text and 'Firm' in header_text and 'Price Target' in header_text:
            for row in rows[1:]:
                cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
                clean = []
                for c in cells:
                    val = re.sub(r'<[^>]+>', '', c).strip()
                    val = html_mod.unescape(val)
                    clean.append(val)
                
                if len(clean) >= 7:
                    analyst = {
                        "analystName": clean[0],
                        "firm": clean[1],
                        "rating": clean[3],
                        "action": clean[4],
                        "priceTarget": clean[5],
                        "upside": clean[6],
                        "date": clean[7] if len(clean) > 7 else ""
                    }
                    result["analysts"].append(analyst)
    
    # Only return if we got analyst data
    if result["analysts"] or result["priceTargets"]["average"]:
        return result
    return None


def push_to_github(data_json, filename="analyst-ratings.json"):
    """Push JSON to GitHub Pages repo"""
    env = {}
    with open("/workspace/.github.env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    
    token = env["GITHUB_TOKEN"]
    user = env["GITHUB_USER"]
    repo = env["GITHUB_REPO"]
    
    content_b64 = base64.b64encode(data_json.encode()).decode()
    
    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{filename}"
    
    # Get current SHA
    req = urllib.request.Request(api_url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    
    current_sha = None
    try:
        resp = urllib.request.urlopen(req)
        file_info = json.loads(resp.read())
        current_sha = file_info["sha"]
    except:
        pass
    
    payload = {
        "message": f"Update analyst-ratings.json — {time.strftime('%Y-%m-%d %H:%M UTC')}",
        "content": content_b64,
    }
    if current_sha:
        payload["sha"] = current_sha
    
    data = json.dumps(payload).encode()
    req2 = urllib.request.Request(api_url, data=data, method="PUT")
    req2.add_header("Authorization", f"token {token}")
    req2.add_header("Accept", "application/vnd.github.v3+json")
    req2.add_header("Content-Type", "application/json")
    
    try:
        resp2 = urllib.request.urlopen(req2)
        result = json.loads(resp2.read())
        return True
    except Exception as e:
        log(f"GitHub push error: {e}")
        return False


def main():
    all_ratings = {}
    success_count = 0
    fail_count = 0
    
    for i, ticker in enumerate(TICKERS):
        try:
            data = fetch_analyst_ratings(ticker)
            if data:
                all_ratings[ticker] = data
                success_count += 1
                n_analysts = len(data["analysts"])
                log(f"✅ {ticker}: {n_analysts} analysts, PT avg=${data['priceTargets']['average']}")
            else:
                fail_count += 1
                log(f"❌ {ticker}: no data")
        except Exception as e:
            fail_count += 1
            log(f"❌ {ticker}: {e}")
        
        # Rate limit — 1 request per second
        time.sleep(1)
    
    log(f"\nSummary: {success_count} success, {fail_count} fail out of {len(TICKERS)} tickers")
    
    # Push to GitHub
    json_str = json.dumps(all_ratings, indent=1)
    if push_to_github(json_str):
        log("✅ Pushed analyst-ratings.json to GitHub Pages")
    else:
        log("❌ Failed to push to GitHub")
    
    # Print errors to stderr only if something went really wrong
    if fail_count > success_count:
        print(f"WARNING: {fail_count} failures out of {len(TICKERS)} tickers", file=sys.stderr)


if __name__ == "__main__":
    main()
    # Silent on success — exit 0 always for cron
    sys.exit(0)
