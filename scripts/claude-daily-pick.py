import os
import requests
from datetime import datetime
import anthropic

os.environ["ANTHROPIC_API_KEY"] = open("/workspace/.github.env").read().split("ANTHROPIC_API_KEY=")[1].split("\n")[0].strip()

FRED_KEY = "593f1942827e82cae99a80669a4756b8"
TELEGRAM_BOT_TOKEN = "8920703462:AAFM4AOt-4-CDBf9s_5DYs7_b1rKY1TkYRQ"
TELEGRAM_CHAT_ID = "8503471418"
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "AMD", "META", "AVGO", "COIN"]
FRED_SERIES = {
    "Fed Funds Rate": "FEDFUNDS",
    "CPI (index)": "CPIAUCSL",
    "Unemployment": "UNRATE",
    "10Y Treasury": "DGS10",
}


def fred_latest(series_id):
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
        f"&sort_order=desc&limit=1"
    )
    obs = requests.get(url, timeout=10).json()["observations"][0]
    return obs["date"], obs["value"]


def macro_snapshot():
    lines = []
    for name, sid in FRED_SERIES.items():
        try:
            date, val = fred_latest(sid)
            lines.append(f"{name}: {val} ({date})")
        except Exception as e:
            lines.append(f"{name}: unavailable ({e})")
    return "\n".join(lines)


def gather_watchlist_data():
    import yfinance as yf
    rows = []
    for t in WATCHLIST:
        try:
            data = yf.Ticker(t).history(period="3mo")
            if data.empty or len(data) < 50:
                continue
            close = data["Close"]
            price = close.iloc[-1]
            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]
            high3mo = close.max()
            low3mo = close.min()
            vol = data["Volume"].iloc[-1]
            avg_vol = data["Volume"].mean()
            rows.append(
                f"{t}: price={price:.2f}, EMA20={ema20:.2f}, EMA50={ema50:.2f}, "
                f"3mo_high={high3mo:.2f}, 3mo_low={low3mo:.2f}, "
                f"vol={vol:,.0f}, avg_vol={avg_vol:,.0f}"
            )
        except Exception:
            continue
    return "\n".join(rows)


def ask_claude(macro, watchlist_data):
    client = anthropic.Anthropic()
    prompt = f"""Here is today's real market data:

MACRO: {macro}

WATCHLIST (3-month price/volume data): {watchlist_data}

Pick the ONE stock with the strongest setup right now (bouncing off support or breaking resistance, confirmed by EMA position and volume). Base your pick ONLY on the numbers above — do not invent any data. In under 100 words, name the ticker, the setup, and the key level to watch. End with a one-line risk-on/off read based on the macro data."""
    msg = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": f"🤖 Claude's Pick — {datetime.now():%b %d}\n\n{message}"})


if __name__ == "__main__":
    macro = macro_snapshot()
    watchlist_data = gather_watchlist_data()
    pick = ask_claude(macro, watchlist_data)
    print(pick)
    send_telegram(pick)
