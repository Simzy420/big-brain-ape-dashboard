#!/usr/bin/env bash
# Payment scanner — checks wallet for new USDC payments every 5 minutes.
# If new payments found, logs to stdout (picked up by cron delivery if local).
# No-agent mode: stdout is the output, empty = silent.
python3.11 /home/hermes/.hermes/scripts/payment-gate.py --scan 2>/dev/null
