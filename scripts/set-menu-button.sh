#!/bin/bash
# Set the Telegram bot menu button to the latest mini app version
# Should run after every gateway restart
BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN /home/hermes/.hermes/.env 2>/dev/null | cut -d'=' -f2)
APP_URL="https://big-brain-ape-trading-bot.github.io/Big-Brain-Ape-Trading-Bot/app32.html"

if [ -z "$BOT_TOKEN" ]; then
    echo "No bot token found"
    exit 1
fi

# Set default menu button for all users
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setChatMenuButton" \
  -H "Content-Type: application/json" \
  -d "{\"menu_button\":{\"type\":\"web_app\",\"text\":\"Open App\",\"web_app\":{\"url\":\"${APP_URL}\"}}}" > /dev/null 2>&1

# Also set for owner specifically
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setChatMenuButton" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\":8503471418,\"menu_button\":{\"type\":\"web_app\",\"text\":\"Open App\",\"web_app\":{\"url\":\"${APP_URL}\"}}}" > /dev/null 2>&1

echo "Menu button set to ${APP_URL}"
