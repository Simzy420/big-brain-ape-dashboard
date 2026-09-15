#!/bin/bash
# Weekly system cleanup for Big Brain Ape bot
# Runs every Sunday at 3 AM UTC

echo "=== WEEKLY CLEANUP STARTED $(date) ==="

# 1. Old dated images (keep _latest only)
find /workspace/output/ -name "*2026*" -mtime +3 -delete 2>/dev/null
echo "Cleaned old dated images"

# 2. Old cron output logs (keep 7 days)
find /home/hermes/.hermes/cron/output/ -name "*.txt" -mtime +7 -delete 2>/dev/null
echo "Cleaned old cron logs"

# 3. Trim error log (keep last 100 lines)
if [ -f /home/hermes/.hermes/logs/errors.log ]; then
  ERR_SIZE=$(stat -c%s /home/hermes/.hermes/logs/errors.log 2>/dev/null || echo 0)
  if [ "$ERR_SIZE" -gt 500000 ]; then
    tail -100 /home/hermes/.hermes/logs/errors.log > /tmp/errors_trimmed.log
    cp /tmp/errors_trimmed.log /home/hermes/.hermes/logs/errors.log
    rm /tmp/errors_trimmed.log
    echo "Error log trimmed (was ${ERR_SIZE} bytes)"
  else
    echo "Error log OK (${ERR_SIZE} bytes)"
  fi
fi

# 4. Trim gateway log (keep last 200 lines)
if [ -f /home/hermes/.hermes/logs/gateway.log ]; then
  GW_SIZE=$(stat -c%s /home/hermes/.hermes/logs/gateway.log 2>/dev/null || echo 0)
  if [ "$GW_SIZE" -gt 500000 ]; then
    tail -200 /home/hermes/.hermes/logs/gateway.log > /tmp/gw_trimmed.log
    cp /tmp/gw_trimmed.log /home/hermes/.hermes/logs/gateway.log
    rm /tmp/gw_trimmed.log
    echo "Gateway log trimmed (was ${GW_SIZE} bytes)"
  else
    echo "Gateway log OK (${GW_SIZE} bytes)"
  fi
fi

# 5. Clean pycache directories
find /workspace -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
echo "Cleaned pycache"

# 6. Clean old cached screenshots (keep mascot source)
find /home/hermes/.hermes/cache/images/ -name "img_*" -mtime +7 -delete 2>/dev/null
echo "Cleaned old cached screenshots"

# 7. Clean tmp git clones
rm -rf /tmp/Big-Brain-Ape-Trading-Bot 2>/dev/null
echo "Cleaned tmp git clones"

# 8. Final summary
echo ""
echo "=== CLEANUP COMPLETE ==="
echo "Disk: $(df -h / | tail -1 | awk '{print $3 " used / " $2 " total (" $5 ")"}')"
echo "Output: $(du -sh /workspace/output/ 2>/dev/null | cut -f1)"
echo "Cron logs: $(du -sh /home/hermes/.hermes/cron/output/ 2>/dev/null | cut -f1)"
echo "Error log: $(ls -lh /home/hermes/.hermes/logs/errors.log 2>/dev/null | awk '{print $5}')"
echo "Gateway log: $(ls -lh /home/hermes/.hermes/logs/gateway.log 2>/dev/null | awk '{print $5}')"
echo "Cache: $(du -sh /home/hermes/.hermes/cache/ 2>/dev/null | cut -f1)"
echo "Tmp: $(du -sh /tmp/ 2>/dev/null | cut -f1)"
