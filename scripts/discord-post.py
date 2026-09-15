#!/usr/bin/env python3.11
"""
Big Brain Ape — Discord Webhook Poster
Sends daily market posts and trade alerts to Discord.

Usage:
  python3.11 discord-post.py --daily     # Post latest daily_post.txt
  python3.11 discord-post.py --trade "NVDA LONG opened at $213.21"
  python3.11 discord-post.py --text "Any message here"
"""
import sys, os, json, datetime, requests

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1546313250608648282/Cv6Zi22DKuGhIEZGsMLesc2G1sgbeoWVxQbkdXIBnadddQJHmfiyv343p4Evc_h3rCUe"
BOT_NAME = "Big Brain Ape 🦍"
APP_URL = "https://simzy420.github.io/big-brain-ape-dashboard/app35.html?owner=1"
PURPLE = 1245824
GREEN = 65312
RED = 16711680

def post_to_discord(embed):
    """Send a rich embed to Discord webhook. Silent on success."""
    # Always include the app link in every post
    embed["fields"] = embed.get("fields", [])
    embed["fields"].append({
        "name": "📊 Live Dashboard",
        "value": f"[Open Big Brain Ape Dashboard]({APP_URL})",
        "inline": False
    })
    payload = {"username": BOT_NAME, "embeds": [embed]}
    try:
        resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=15)
        return resp.status_code == 204
    except Exception as e:
        print(f"Discord post failed: {e}", file=sys.stderr)
        return False

def post_daily():
    """Read latest daily market post and send to Discord."""
    post_file = "/workspace/daily_post.txt"
    if not os.path.exists(post_file):
        print("No daily_post.txt found", file=sys.stderr)
        sys.exit(0)

    with open(post_file) as f:
        text = f.read().strip()

    if not text:
        sys.exit(0)

    # Discord embeds: 4096 char description limit
    if len(text) > 4000:
        desc = text[:4000] + "\n\n*(Full thread on X @Big_Brain_Ape)*"
    else:
        desc = text

    embed = {
        "title": "📊 Daily Market Snapshot",
        "description": desc,
        "color": PURPLE,
        "footer": {"text": "Big Brain Ape · Fully Autonomous AI Trading Bot"},
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    ok = post_to_discord(embed)
    sys.exit(0 if ok else 1)

def post_trade(message):
    """Send a trade alert to Discord."""
    embed = {
        "title": "⚡ Trade Alert",
        "description": message,
        "color": GREEN,
        "footer": {"text": "Big Brain Ape · Hyperliquid Perp Futures"},
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    ok = post_to_discord(embed)
    sys.exit(0 if ok else 1)

def post_text(message):
    """Send a plain text message to Discord."""
    embed = {
        "description": message,
        "color": PURPLE,
        "footer": {"text": "Big Brain Ape"},
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    ok = post_to_discord(embed)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: discord-post.py --daily | --trade 'msg' | --text 'msg'")
        sys.exit(0)

    if "--daily" in args:
        post_daily()
    elif "--trade" in args:
        idx = args.index("--trade")
        msg = args[idx + 1] if idx + 1 < len(args) else ""
        post_trade(msg)
    elif "--text" in args:
        idx = args.index("--text")
        msg = args[idx + 1] if idx + 1 < len(args) else ""
        post_text(msg)
    else:
        post_text(" ".join(args))
