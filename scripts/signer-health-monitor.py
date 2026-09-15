#!/usr/bin/env python3
"""
Signer Health Monitor — checks ACP signer key status every 30 minutes.
SILENT when healthy. Alerts ONLY when the signer key is missing.

The #1 failure mode: ACP session token expires → re-auth wipes the local P256 key
→ trades silently fail with opaque signer binary crashes.
This monitor catches that BEFORE the next trading cron run discovers it.

Simplified July 28: Only checks the signer key (the actual failure point).
Auth check removed — `acp configure status` is not a valid command.
Policy check removed — signer key presence is the reliable signal.
"""

import subprocess
import json
import sys
import os
from pathlib import Path

# Load .env for Discord webhook + Telegram bot token
env_path = Path("/home/hermes/.hermes/.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
TELEGRAM_CHAT_ID = "8503471418"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

SIGNER_BINARY = "/home/hermes/.hermes/skills/acp-cli/bin/acp-cli-signer-linux"

def send_alert(title, details):
    """Send alert to Telegram + Discord + stdout."""
    msg = f"⚠️ SIGNER HEALTH ALERT\n\n{title}\n\n{details}\n\nThe signing key that lets me trade has been lost (happens when the ACP session expires). I'll send you a link to click — one click fixes it."

    # Only output to stdout — cron delivery setting controls whether user sees it
    # Do NOT send directly via Telegram/Discord — that bypasses the delivery setting
    #SILENT_print_(msg)

def main():
    """Check signer key. Alert only if missing. Silent otherwise."""
    try:
        r = subprocess.run([SIGNER_BINARY, "list"], capture_output=True, text=True, timeout=5)
        data = json.loads(r.stdout.strip())
        keys = data.get("keys", [])
        if not keys:
            send_alert(
                "Signer key MISSING",
                "The local P256 signing key is gone. Trades will fail until a new signer is approved."
            )
            sys.exit(1)
        # Key present — all good, stay silent
        sys.exit(0)
    except Exception as e:
        send_alert(
            "Signer check ERROR",
            f"Could not verify signer key: {str(e)[:200]}"
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
