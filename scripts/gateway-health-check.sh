#!/bin/bash
# Gateway health check — restarts gateway if it's down
# Runs as a no_agent=True cron job every 5 minutes
export PATH="/opt/hermes-agent/venv/bin:$PATH"
export TELEGRAM_FALLBACK_IPS="149.154.166.110,149.154.167.220"
export HOME="/home/hermes"

# Check if gateway is running
if hermes gateway status 2>&1 | grep -q "Gateway is running"; then
    # Gateway is fine, nothing to do
    exit 0
fi

# Gateway is down — restart it
echo "$(date): Gateway down, restarting..." 

# Kill any stale processes
pkill -9 -f "hermes gateway" 2>/dev/null
sleep 2
rm -f /home/hermes/.hermes/gateway/gateway.pid

# Clear stale Telegram polling session
source /home/hermes/.hermes/.env 2>/dev/null
curl -s --connect-timeout 5 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" > /dev/null 2>&1
sleep 3

# Start fresh gateway
hermes gateway run --replace >> /home/hermes/.hermes/gateway/gateway.log 2>&1 &
GWPID=$!
echo "$GWPID" > /home/hermes/.hermes/gateway/gateway.pid

# Wait for it to connect
sleep 15

# Verify
if hermes gateway status 2>&1 | grep -q "Gateway is running"; then
    echo "$(date): Gateway restarted successfully (PID $GWPID)"
else
    echo "$(date): Gateway failed to start"
fi
