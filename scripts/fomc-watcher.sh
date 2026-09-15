#!/bin/bash
# FOMC Live Watcher - searches web for latest FOMC news and outputs a breakdown
# Called by cron jobs every 10 minutes during FOMC meeting

echo "FOMC LIVE WATCHER - $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "---"
echo "Searching for latest FOMC news..."
