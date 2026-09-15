# Big Brain Ape — Backend Scripts

Server-side scripts that power Big Brain Ape's automated operations.

## Categories

- **Trading**: `snapshot-gen.py`, `update-trading-posts.py`, `performance-fee.py`, `ta-analysis.py`
- **Market Data**: `macro-data-fetch.py`, `fmp-data-fetch.py`, `twelvedata-fetch.py`, `yahoo-data.py`, `keyless-data-fetch.py`, `ticker-cache-generator.py`
- **News & Analysis**: `jina-news-scraper.py`, `fetch-analyst-ratings.py`, `daily-briefing-generator.py`, `claude-daily-pick.py`
- **Social Media**: `auto-campaign-post.py`, `discord-post.py`, `x-engagement.py`
- **Marketplace**: `dealwork-monitor.py`, `marketplace-cron.sh`, `marketplace-monitor.sh`
- **Infrastructure**: `gateway-health-check.sh`, `signer-health-monitor.py`, `weekly-cleanup.sh`, `fix-cron-deliver.sh`, `set-menu-button.sh`, `payment-scan.sh`
- **Chat**: `bba-chat-server.py`
- **FOMC**: `fomc-watcher.sh`

## Note

Scripts that contain API keys, wallet addresses, or other secrets are NOT included in this repo.
They read credentials from environment variables or `.env` files (which are in `.gitignore`).
