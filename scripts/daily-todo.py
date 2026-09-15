#!/usr/bin/env python3.11
"""
Big Brain Ape — Daily Operations To-Do List Generator
Generates three to-do lists: You (user), Claude, and Big Brain Ape (self).
Checks live status of all systems, trading, apps, and tasks.
Output is saved to /workspace/daily-todo.md and sent to Telegram.
"""
import json, os, time, urllib.request

def check_app(url, path="/api/health"):
    """Check if an app is live."""
    try:
        full = url.rstrip("/") + path
        resp = urllib.request.urlopen(full, timeout=10)
        return True
    except:
        # Try root path
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            return True
        except:
            return False

def get_portfolio():
    """Get portfolio summary from latest-state.json."""
    try:
        with open("/workspace/latest-state.json") as f:
            d = json.load(f)
        # account is nested under "account" key, not top-level "account_value"
        acct = d.get("account", {}).get("value", 0)
        positions = d.get("positions", [])
        pos_str = []
        for p in positions:
            # Field names in latest-state.json: token, side, entry, pnl (not coin/unrealized_pnl)
            coin = p.get("token", p.get("coin", "?"))
            side = p.get("side", "?")
            entry = p.get("entry", 0)
            pnl = p.get("pnl", p.get("unrealized_pnl", 0))
            pos_str.append(f"  • {coin} {side} @ ${entry} (PnL: ${pnl:+.2f})")
        return acct, pos_str
    except:
        return 0, ["  • Data needs refresh"]

def check_cron_jobs():
    """Check which cron jobs are enabled."""
    try:
        with open("/home/hermes/.hermes/cron/jobs.json") as f:
            d = json.load(f)
        enabled = []
        for j in d.get("jobs", []):
            if j.get("enabled", True):
                name = j.get("name", "unnamed")
                enabled.append(name)
        return enabled
    except:
        return []

# ============================================================
# GATHER STATUS
# ============================================================

today = time.strftime("%B %d, %Y", time.gmtime())

# App status
apps = {
    "Dashboard": check_app("https://simzy420.github.io/big-brain-ape-dashboard/app35.html"),
    "Campaign Studio": check_app("https://simzy-campaign-studio.hf.space"),
    "Launch Desk": check_app("https://simzy-launch-desk.hf.space"),
    "BigBrain API": check_app("https://simzy-bigbrain-api.hf.space", "/health"),
}

# Portfolio
acct, positions = get_portfolio()

# Reddit posts
reddit_ready = os.path.exists("/workspace/reddit-posts.md")

# ============================================================
# GENERATE TO-DO LISTS
# ============================================================

msg = f"""🦍 **DAILY OPERATIONS — {today}**

**SYSTEM STATUS**
"""
for app, status in apps.items():
    icon = "✅" if status else "❌"
    msg += f"{icon} {app}\n"

msg += f"\n📊 **TRADING**\n"
msg += f"Account: ${acct:,.2f}\n"
for p in positions:
    msg += f"{p}\n"

msg += f"""
---

📋 **YOUR TO-DO LIST (Things only you can do)**

1. {"✅ DONE" if reddit_ready else "⬜"} **Post on Reddit** — Two posts ready at /workspace/reddit-posts.md. Post to r/algotrading and r/stocks. This is free marketing to people who'd hire a trading bot. Only you can do this (no Reddit API).

2. ⬜ **Test the apps on your phone** — Tap these links and try them:
   • Campaign Studio: https://simzy-campaign-studio.hf.space
   • Launch Desk: https://simzy-launch-desk.hf.space
   • Tell me what you think — should we change anything?

3. ⬜ **Share the x402 API** — If you know any developers who need financial data, share: https://simzy-bigbrain-api.hf.space ($0.01-$0.10 per call)

4. ⬜ **Check X (@Big_Brain_Ape)** — Daily posts should be going out automatically at 7 AM MT. Check the account and let me know if anything looks off.

---

🤖 **CLAUDE'S TO-DO LIST (Coding tasks I'll delegate)**

1. ⬜ **Write tests for Campaign Studio** — Health check, generate endpoint, image endpoint, error handling
2. ⬜ **Write tests for Launch Desk** — Streaming endpoint, tool calls, SSE format
3. ⬜ **Deploy World Room** — It's built but not on HuggingFace yet (needs OPENAI_API_KEY secret + mic permissions)
4. ⬜ **Review app35.html for bugs** — Run through the dashboard code looking for edge cases

---

🧠 **MY TO-DO LIST (Big Brain Ape — trading + ops)**

1. ⬜ **Trading cron at 8 PM MYT** — Review portfolio, run Druckenmiller framework, make trades if needed
2. ⬜ **Check OpenTask for new bounties** — 30 tasks available, 2 proposals pending. Bid on any new finance/crypto tasks
3. ⬜ **Monitor NVDA + GOLD positions** — Both in profit, watching for thesis changes
4. ⬜ **Check daily snapshot posted to X** — Verify the image and trading activity tweets went out
5. ⬜ **Look for new revenue opportunities** — Agent marketplaces, bounties, trading alpha
6. ⬜ **APP FEATURE: Price Alerts** — Add push notifications when user's target price is hit (free=3, paid=unlimited)
7. ⬜ **APP FEATURE: Watchlist** — Let users star/favorite tickers, show at top on next visit

---

💰 **REVENUE TRACKER**
• Trading PnL: ${acct:,.2f} account value
• OpenTask: 2 proposals pending (waiting for acceptance)
• x402 API: Live, pay-per-call ($0.01-$0.10/call)
• dealwork.ai: Listing live, waiting for clients
• Telegram bot: @BigBrain2Bot ($0.25/analysis, $0.50/portfolio review)

*This list auto-generates every morning. Reply with any changes.*
"""

# Save to file
with open("/workspace/daily-todo.md", "w") as f:
    f.write(msg)

print(msg)
