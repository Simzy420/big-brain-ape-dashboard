#!/bin/bash
# Marketplace Monitor — checks for incoming trading jobs
# Run every 15 minutes via cron
# Silent when no jobs, alerts when action needed

EVENTS_FILE="/home/hermes/.hermes/marketplace/events.jsonl"
ALERT_FILE="/home/hermes/.hermes/marketplace/job-alert.txt"
STATE_FILE="/home/hermes/.hermes/marketplace/last-check.txt"

# 1. Check if listener is alive
LISTENER_ALIVE=false
for f in /proc/*/cmdline; do
  cmd=$(cat "$f" 2>/dev/null | tr '\0' ' ')
  if echo "$cmd" | grep -q "acp events listen"; then
    LISTENER_ALIVE=true
    break
  fi
done

if [ "$LISTENER_ALIVE" = false ]; then
  echo "ALERT: Events listener is NOT running. Restart needed." > "$ALERT_FILE"
  # Try to restart
  mkdir -p /home/hermes/.hermes/marketplace
  nohup acp events listen --output "$EVENTS_FILE" --json > /home/hermes/.hermes/marketplace/listener.log 2>&1 &
  echo "Listener restarted at $(date)" >> "$ALERT_FILE"
  cat "$ALERT_FILE"
  exit 0
fi

# 2. Drain any events
if [ ! -f "$EVENTS_FILE" ]; then
  # No events file = no events yet, all quiet
  echo "$(date): OK - listener alive, no events" > "$STATE_FILE"
  exit 0
fi

DRAIN_OUTPUT=$(acp events drain --file "$EVENTS_FILE" --limit 10 --json 2>/dev/null)

if [ -z "$DRAIN_OUTPUT" ]; then
  echo "$(date): OK - listener alive, drain returned empty" > "$STATE_FILE"
  exit 0
fi

# 3. Parse events for actionable jobs
EVENTS=$(echo "$DRAIN_OUTPUT" | python3 -c "
import sys, json

try:
    data = json.load(sys.stdin)
except:
    print('PARSE_ERROR')
    sys.exit(0)

events = data.get('events', [])
if not events:
    print('NO_EVENTS')
    sys.exit(0)

for e in events:
    job_id = e.get('jobId', 'unknown')
    status = e.get('status', 'unknown')
    roles = e.get('roles', [])
    tools = e.get('availableTools', [])
    entry = e.get('entry', {})
    
    # Job created — someone hired us
    if status == 'open' or 'job.created' in str(entry.get('event', {}).get('type', '')):
        print(f'JOB_CREATED|{job_id}|{status}|{\",\".join(tools)}')
    
    # Budget set — provider needs to set budget (we are provider)
    elif status == 'budget_set':
        amount = entry.get('event', {}).get('amount', 'unknown')
        print(f'BUDGET_SET|{job_id}|{status}|{amount}|{\",\".join(tools)}')
    
    # Funded — client funded escrow, we need to do the work
    elif status == 'funded':
        print(f'JOB_FUNDED|{job_id}|{status}|{\",\".join(tools)}')
    
    # Submitted — we submitted deliverable, waiting for client
    elif status == 'submitted':
        print(f'JOB_SUBMITTED|{job_id}|{status}|{\",\".join(tools)}')
    
    # Completed — escrow released to us
    elif status == 'completed':
        print(f'JOB_COMPLETED|{job_id}|{status}')
    
    # Rejected
    elif status == 'rejected':
        reason = entry.get('event', {}).get('reason', 'no reason given')
        print(f'JOB_REJECTED|{job_id}|{status}|{reason}')
    
    # Expired
    elif status == 'expired':
        print(f'JOB_EXPIRED|{job_id}|{status}')
    
    else:
        print(f'OTHER|{job_id}|{status}|{\",\".join(tools)}')
" 2>/dev/null)

# 4. Process results
if [ "$EVENTS" = "NO_EVENTS" ] || [ -z "$EVENTS" ]; then
  echo "$(date): OK - listener alive, no new events" > "$STATE_FILE"
  exit 0
fi

if [ "$EVENTS" = "PARSE_ERROR" ]; then
  echo "$(date): WARN - drain output parse error" > "$STATE_FILE"
  exit 0
fi

# 5. We have actionable events — write alert file
echo "MARKETPLACE JOB ALERT — $(date)" > "$ALERT_FILE"
echo "" >> "$ALERT_FILE"
echo "$EVENTS" >> "$ALERT_FILE"
echo "" >> "$ALERT_FILE"
echo "Raw drain output:" >> "$ALERT_FILE"
echo "$DRAIN_OUTPUT" >> "$ALERT_FILE"

cat "$ALERT_FILE"
