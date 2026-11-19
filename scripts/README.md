# Big Brain Ape — Backend Scripts

Server-side scripts that power Big Brain Ape's automated operations.

## Categories

- **Trading**: `snapshot-gen.py`, `update-trading-posts.py`, `performance-fee.py`, `ta-analysis.py`
- **Market Data**: `macro-data-fetch.py`, `fmp-data-fetch.py`, `twelvedata-fetch.py`, `yahoo-data.py`, `keyless-data-fetch.py`, `ticker-cache-generator.py`
- **News & Analysis**: `jina-news-scraper.py`, `fetch-analyst-ratings.py`, `daily-briefing-generator.py`, `claude-daily-pick.py`
- **Social Media**: `auto-campaign-post.py`, `discord-post.py`, `x-engagement.py`
- **Marketplace**: `dealwork-monitor.py`, `marketplace-cron.sh`, `marketplace-monitor.sh`
- **Infrastructure**: `gateway-health-check.sh`, `signer-health-monitor.py`, `weekly-cleanup.sh`, `force-cron-deliver.sh`, `set-menu-button.sh`, `payment-scan.sh`
- **Corrigo inbox**: `corrigo-gmail-fetch.py`, `corrigo-email-scan.py`, `corrigo-inbox-sync.py` (GitHub Actions poll every 5m: `.github/workflows/corrigo-email-sync.yml`)
- **Chat**: `bba-chat-server.py`
- **FOMC**: `fomc-watcher.sh`

### Corrigo Gmail → Inbox

```bash
# Dry-run (needs COMPOSIO_API_KEY + COMPOSIO_CONNECTED_ACCOUNT_ID)
python3 scripts/corrigo-inbox-sync.py --dry-run

# Live: fetch Gary/Corrigo mail, update work-orders.json, commit+push
python3 scripts/corrigo-inbox-sync.py --push
```

Idempotent: `corrigo-email-scan.py` skips WOs already in `work-orders.json` / `corrigo-overrides.json` (normalized numbers, renames, removals).

## Note

Scripts that contain API keys, wallet addresses, or other secrets are NOT included in this repo.
They read credentials from environment variables or `.env` files (which are in `.gitignore`).
