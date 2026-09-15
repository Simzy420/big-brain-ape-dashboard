#!/bin/bash
# Marketplace monitor + job handler — runs via cron every 15 minutes
# Checks for events, processes any actionable jobs, alerts user if needed
# Silent when nothing to report

EVENTS_FILE="/home/hermes/.hermes/marketplace/events.jsonl"
HANDLER="/home/hermes/.hermes/scripts/trading-job-handler.py"
MONITOR="/home/hermes/.hermes/scripts/marketplace-monitor.sh"
OUTPUT_DIR="/home/hermes/.hermes/marketplace"

mkdir -p "$OUTPUT_DIR"

# Step 1: Run the monitor script
MONITOR_OUTPUT=$(bash "$MONITOR" 2>&1)

# Step 2: Check if there's a job alert
ALERT_FILE="$OUTPUT_DIR/job-alert.txt"
if [ -f "$ALERT_FILE" ]; then
  # We have events — check if any need the handler
  EVENTS=$(acp events drain --file "$EVENTS_FILE" --limit 10 --json 2>/dev/null)
  
  if [ -n "$EVENTS" ]; then
    # Parse events and run handler for each actionable one
    echo "$EVENTS" | python3 -c "
import sys, json, subprocess

try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)

events = data.get('events', [])
for e in events:
    status = e.get('status', '')
    if status in ('open', 'budget_set', 'funded', 'completed', 'rejected', 'expired'):
        # Run the handler for this event
        event_json = json.dumps(e)
        result = subprocess.run(
            ['python3.11', '$HANDLER', '--event', event_json],
            capture_output=True, text=True, timeout=120
        )
        print(result.stdout)
        if result.stderr:
            print(f'STDERR: {result.stderr}')
        print('---')
" 2>&1
    
    # Output the alert for the cron to deliver
    echo "MARKETPLACE ACTIVITY DETECTED"
    echo ""
    cat "$ALERT_FILE"
    
    # Clear the alert after processing
    rm -f "$ALERT_FILE"
  fi
fi

# Step 3: Health check — verify listener alive
LISTENER_ALIVE=false
for f in /proc/*/cmdline; do
  cmd=$(cat "$f" 2>/dev/null | tr '\0' ' ')
  if echo "$cmd" | grep -q "acp events listen"; then
    LISTENER_ALIVE=true
    break
  fi
done

if [ "$LISTENER_ALIVE" = false ]; then
  echo "ALERT: Events listener died. Attempting restart..."
  nohup acp events listen --output "$EVENTS_FILE" --json > "$OUTPUT_DIR/listener.log" 2>&1 &
  echo "Listener restarted."
fi

# If nothing happened, stay silent
if [ ! -f "$ALERT_FILE" ]; then
  # Quiet exit — no output means cron won't spam the user
  exit 0
fi
