#!/usr/bin/env python3
"""
BBA Dashboard Data Updater — Master Script
============================================
Updates all JSON data files for the Big Brain Ape dashboard.
Pushes to GitHub Pages repo automatically.

Usage:
  python3 dashboard-update.py [mode]

Modes:
  full     — all data files (default, for 12h cron)
  markets  — just markets.json (for 5-min cron)
  news     — just news.json (for 2h cron)
  compute  — just compute-balance.json (for 12h cron)
  positions — just positions.json (for 12h cron)
"""
import json, os, sys, time, subprocess, requests
from datetime import datetime, timezone

REPO_DIR = "/workspace/big-brain-ape-dashboard"
ENV_FILE = "/workspace/.github.env"
GITHUB_USER = "Simzy420"
GITHUB_REPO = "big-brain-ape-dashboard"
GITHUB_BRANCH = "main"

# API keys (embedded in app35.html, same ones)
FMP_KEY = "FYPPeClubVq4A3KcyNkDH5S1g2Rw1SCL"
FINNHUB_KEY = "d9dpmp9r01qujggob290d9dpmp9r01qujggob29g"

def load_github_token():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GITHUB_TOKEN_SIMZY="):
                return line.split("=", 1)[1]
            elif line.startswith("GITHUB_TOKEN=") and not line.startswith("GITHUB_TOKEN_SIMZY="):
                return line.split("=", 1)[1]
    return None

GH_TOKEN = load_github_token()

def github_push(filename, content_str, commit_msg):
    """Push a file to GitHub via the Contents API."""
    import base64
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    # Get current sha
    r = requests.get(url, headers=headers, timeout=15)
    sha = r.json().get("sha") if r.status_code == 200 else None
    
    data = {
        "message": commit_msg,
        "content": base64.b64encode(content_str.encode()).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        data["sha"] = sha
    
    r = requests.put(url, headers=headers, json=data, timeout=30)
    return r.status_code in (200, 201)

def local_save(filename, content_str):
    """Save to local repo dir."""
    path = os.path.join(REPO_DIR, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content_str)
    return path

# ─────────── POSITIONS ───────────

def update_positions():
    """Get live positions from Hyperliquid via ACP CLI."""
    print("Updating positions.json...")
    try:
        result = subprocess.run(
            ["acp", "trade", "hl-status", "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            # Write as-is
            content = json.dumps(data, indent=2)
            local_save("positions.json", content)
            github_push("positions.json", content, f"Auto-update positions {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            print("  ✓ positions.json updated")
            return True
    except Exception as e:
        print(f"  ✗ positions.json failed: {e}")
    return False

# ─────────── COMPUTE BALANCE ───────────

def update_compute():
    """Get compute balance from ACP CLI."""
    print("Updating compute-balance.json...")
    try:
        result = subprocess.run(
            ["acp", "compute", "status", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout:
            d = json.loads(result.stdout)
            data = {
                "limit": round(d.get("limit", 0), 2),
                "remaining": round(d.get("limitRemaining", d.get("limit", 0)), 2),
                "totalUsage": round(d.get("usage", 0), 2),
                "updated": datetime.now(timezone.utc).isoformat(),
            }
            content = json.dumps(data, indent=2)
            local_save("compute-balance.json", content)
            # Also save to command-center
            cc_path = "/workspace/command-center/public/compute-balance.json"
            if os.path.exists(os.path.dirname(cc_path)):
                with open(cc_path, "w") as f:
                    f.write(content)
            github_push("compute-balance.json", content, f"Auto-update compute balance {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
            print("  ✓ compute-balance.json updated")
            return True
    except Exception as e:
        print(f"  ✗ compute-balance.json failed: {e}")
    return False

# ─────────── MARKETS (XYZ perps + crypto) ───────────

def update_markets():
    """Fetch XYZ perps prices and crypto prices from free APIs."""
    print("Updating markets.json...")
    try:
        # Crypto from CoinGecko (free)
        cg_url = "https://api.coingecko.com/api/v3/simple/price"
        crypto_ids = {
            "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
            "HYPE": "hyperliquid", "AVAX": "avalanche-2", "BNB": "binancecoin",
        }
        cg_params = {
            "ids": ",".join(crypto_ids.values()),
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }
        cg_resp = requests.get(cg_url, params=cg_params, timeout=10)
        cg_data = cg_resp.json() if cg_resp.status_code == 200 else {}

        markets = {}
        for sym, coin_id in crypto_ids.items():
            if coin_id in cg_data:
                markets[sym] = {
                    "price": cg_data[coin_id].get("usd", 0),
                    "change24h": cg_data[coin_id].get("usd_24h_change", 0),
                    "source": "CoinGecko",
                }

        # XYZ perps from Finnhub (free key)
        xyz_symbols = {
            "NVDA": "NVDA", "AAPL": "AAPL", "MSFT": "MSFT", "GOOGL": "GOOGL",
            "AMZN": "AMZN", "META": "META", "TSLA": "TSLA", "AMD": "AMD",
            "GOLD": "GC=F", "SILVER": "SI=F", "BRENTOIL": "BZ=F", "CL": "CL=F",
            "SP500": "^GSPC", "DXY": "DX-Y.NYB", "EUR": "EURUSD=X",
            "JPY": "JPY=X", "PLATINUM": "PL=F", "COPPER": "HG=F",
            "NFLX": "NFLX", "ORCL": "ORCL", "TSM": "TSM", "COIN": "COIN",
        }
        for sym, yf_sym in xyz_symbols.items():
            try:
                fh_url = f"https://finnhub.io/api/v1/quote?symbol={yf_sym}&token={FINNHUB_KEY}"
                fh_resp = requests.get(fh_url, timeout=5)
                if fh_resp.status_code == 200:
                    d = fh_resp.json()
                    if d.get("c", 0) > 0:
                        markets[sym] = {
                            "price": d["c"],
                            "change24h": d.get("dp", 0),
                            "source": "Finnhub",
                        }
            except:
                pass

        data = {
            "markets": markets,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        content = json.dumps(data, indent=2)
        local_save("markets.json", content)
        github_push("markets.json", content, f"Auto-update markets {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"  ✓ markets.json updated ({len(markets)} symbols)")
        return True
    except Exception as e:
        print(f"  ✗ markets.json failed: {e}")
    return False

# ─────────── SNAPSHOT ───────────

def update_snapshot():
    """Run snapshot-gen.py which fetches market data and pushes to GitHub."""
    print("Updating snapshot.json...")
    try:
        result = subprocess.run(
            ["python3", os.path.join(REPO_DIR, "scripts", "snapshot-gen.py")],
            capture_output=True, text=True, timeout=120,
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            print("  ✓ snapshot.json updated")
            return True
        else:
            print(f"  ✗ snapshot.json failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ✗ snapshot.json failed: {e}")
    return False

# ─────────── STOCK DATA ───────────

def update_stock_data():
    """Run fmp-data-fetch.py for stock analysis data."""
    print("Updating stock-data.json...")
    try:
        result = subprocess.run(
            ["python3", os.path.join(REPO_DIR, "scripts", "fmp-data-fetch.py")],
            capture_output=True, text=True, timeout=120,
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            print("  ✓ stock-data.json updated")
            return True
        else:
            print(f"  ✗ stock-data.json failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ✗ stock-data.json failed: {e}")
    return False

# ─────────── ANALYST RATINGS ───────────

def update_analyst_ratings():
    """Run fetch-analyst-ratings.py."""
    print("Updating analyst-ratings.json...")
    try:
        result = subprocess.run(
            ["python3", os.path.join(REPO_DIR, "scripts", "fetch-analyst-ratings.py")],
            capture_output=True, text=True, timeout=120,
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            print("  ✓ analyst-ratings.json updated")
            return True
        else:
            print(f"  ✗ analyst-ratings.json failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ✗ analyst-ratings.json failed: {e}")
    return False

# ─────────── NEWS ───────────

def update_news():
    """Run jina-news-scraper.py."""
    print("Updating news.json...")
    try:
        result = subprocess.run(
            ["python3", os.path.join(REPO_DIR, "scripts", "jina-news-scraper.py")],
            capture_output=True, text=True, timeout=120,
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            # The script writes to its own output, copy to repo root
            news_path = os.path.join(REPO_DIR, "news.json")
            if os.path.exists(news_path):
                with open(news_path) as f:
                    content = f.read()
                github_push("news.json", content, f"Auto-update news {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
                print("  ✓ news.json updated")
                return True
        else:
            print(f"  ✗ news.json failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ✗ news.json failed: {e}")
    return False

# ─────────── TRADING POSTS ───────────

def update_trading_posts():
    """Run update-trading-posts.py."""
    print("Updating trading-posts.json...")
    try:
        result = subprocess.run(
            ["python3", os.path.join(REPO_DIR, "scripts", "update-trading-posts.py")],
            capture_output=True, text=True, timeout=60,
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            print("  ✓ trading-posts.json updated")
            return True
        else:
            print(f"  ✗ trading-posts.json failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ✗ trading-posts.json failed: {e}")
    return False

# ─────────── MAIN ───────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    
    if mode == "full":
        update_positions()
        update_compute()
        update_snapshot()
        update_stock_data()
        update_analyst_ratings()
        update_news()
        update_trading_posts()
    elif mode == "markets":
        update_markets()
    elif mode == "news":
        update_news()
    elif mode == "compute":
        update_compute()
    elif mode == "positions":
        update_positions()
    elif mode == "snapshot":
        update_snapshot()
    elif mode == "stocks":
        update_stock_data()
        update_analyst_ratings()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 dashboard-update.py [full|markets|news|compute|positions|snapshot|stocks]")
        sys.exit(1)
    
    print(f"\nDone ({mode}) at {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()
