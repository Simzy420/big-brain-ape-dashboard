#!/usr/bin/env python3
"""
Performance Fee Calculator with High-Water Mark

Tracks client capital, high-water mark, and calculates the 20% performance fee.
Each client job gets its own ledger file.

Usage:
  python3 performance-fee.py init <job_id> <initial_capital_usd>
  python3 performance-fee.py update <job_id> <current_value_usd>
  python3 performance-fee.py settle <job_id> <final_value_usd>
  python3 performance-fee.py status <job_id>
"""

import json
import os
import sys
from datetime import datetime

LEDGER_DIR = "/home/hermes/.hermes/marketplace/ledgers"
PERFORMANCE_FEE_RATE = 0.20  # 20%

def ledger_path(job_id):
    return os.path.join(LEDGER_DIR, f"{job_id}.json")

def init(job_id, initial_capital):
    """Initialize a client ledger with their starting capital."""
    os.makedirs(LEDGER_DIR, exist_ok=True)
    ledger = {
        "job_id": job_id,
        "initial_capital": float(initial_capital),
        "high_water_mark": float(initial_capital),
        "current_value": float(initial_capital),
        "realized_profit": 0.0,
        "fees_earned": 0.0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "snapshots": []
    }
    with open(ledger_path(job_id), 'w') as f:
        json.dump(ledger, f, indent=2)
    print(f"Ledger initialized for job {job_id}")
    print(f"  Initial capital: ${initial_capital}")
    print(f"  High-water mark: ${initial_capital}")
    return ledger

def update(job_id, current_value):
    """Record current portfolio value. Calculates accrued fees if new HWM."""
    path = ledger_path(job_id)
    if not os.path.exists(path):
        print(f"ERROR: No ledger found for job {job_id}. Run init first.")
        return
    
    with open(path) as f:
        ledger = json.load(f)
    
    current_value = float(current_value)
    old_hwm = ledger["high_water_mark"]
    
    # New profit above high-water mark
    new_profit_above_hwm = max(0, current_value - old_hwm)
    accrued_fee = new_profit_above_hwm * PERFORMANCE_FEE_RATE
    
    # Update high-water mark if we hit a new peak
    if current_value > old_hwm:
        ledger["high_water_mark"] = current_value
    
    ledger["current_value"] = current_value
    ledger["updated_at"] = datetime.utcnow().isoformat()
    
    # Add snapshot
    ledger["snapshots"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "value": current_value,
        "hwm_at_time": ledger["high_water_mark"],
        "profit_above_hwm": new_profit_above_hwm,
        "accrued_fee": accrued_fee
    })
    
    # Keep only last 100 snapshots
    if len(ledger["snapshots"]) > 100:
        ledger["snapshots"] = ledger["snapshots"][-100:]
    
    with open(path, 'w') as f:
        json.dump(ledger, f, indent=2)
    
    total_profit = current_value - ledger["initial_capital"]
    print(f"Updated job {job_id}")
    print(f"  Current value:   ${current_value:.2f}")
    print(f"  High-water mark: ${ledger['high_water_mark']:.2f}")
    print(f"  Total P&L:       ${total_profit:+.2f}")
    print(f"  Accrued fee:     ${accrued_fee:.2f}")
    return ledger

def settle(job_id, final_value):
    """Final settlement — calculate final fee and client return."""
    path = ledger_path(job_id)
    if not os.path.exists(path):
        print(f"ERROR: No ledger found for job {job_id}. Run init first.")
        return
    
    with open(path) as f:
        ledger = json.load(f)
    
    final_value = float(final_value)
    initial = ledger["initial_capital"]
    
    # Final profit
    total_profit = final_value - initial
    
    if total_profit <= 0:
        # No profit, no fee
        fee = 0.0
        client_return = final_value
        result = "NO PROFIT — no fee charged"
    else:
        # 20% of profit
        fee = total_profit * PERFORMANCE_FEE_RATE
        client_return = final_value - fee
        result = f"PROFIT — 20% fee = ${fee:.2f}"
    
    # Update ledger
    ledger["current_value"] = final_value
    ledger["realized_profit"] = total_profit
    ledger["fees_earned"] = fee
    ledger["settled_at"] = datetime.utcnow().isoformat()
    ledger["settlement"] = {
        "final_value": final_value,
        "total_profit": total_profit,
        "fee_rate": PERFORMANCE_FEE_RATE,
        "fee_amount": fee,
        "client_return": client_return,
        "result": result
    }
    
    with open(path, 'w') as f:
        json.dump(ledger, f, indent=2)
    
    print(f"SETTLEMENT for job {job_id}")
    print(f"  Initial capital: ${initial:.2f}")
    print(f"  Final value:     ${final_value:.2f}")
    print(f"  Total profit:    ${total_profit:+.2f}")
    print(f"  Performance fee: ${fee:.2f} (20% of profit)")
    print(f"  Client receives: ${client_return:.2f}")
    print(f"  Result: {result}")
    print(f"")
    print(f"  ACTION: Send ${client_return:.2f} USDC to client wallet.")
    print(f"  Keep ${fee:.2f} USDC as performance fee.")
    return ledger

def status(job_id):
    """Show current ledger status."""
    path = ledger_path(job_id)
    if not os.path.exists(path):
        print(f"No ledger found for job {job_id}")
        return
    
    with open(path) as f:
        ledger = json.load(f)
    
    total_profit = ledger["current_value"] - ledger["initial_capital"]
    accrued = max(0, ledger["current_value"] - ledger["high_water_mark"]) * PERFORMANCE_FEE_RATE
    
    print(f"LEDGER STATUS for job {job_id}")
    print(f"  Created:          {ledger.get('created_at', 'N/A')}")
    print(f"  Initial capital:  ${ledger['initial_capital']:.2f}")
    print(f"  Current value:    ${ledger['current_value']:.2f}")
    print(f"  High-water mark:  ${ledger['high_water_mark']:.2f}")
    print(f"  Total P&L:        ${total_profit:+.2f}")
    print(f"  Fees earned:      ${ledger.get('fees_earned', 0):.2f}")
    print(f"  Settled:          {'Yes' if 'settled_at' in ledger else 'No'}")
    if "settlement" in ledger:
        s = ledger["settlement"]
        print(f"  Settlement:       ${s['client_return']:.2f} to client, ${s['fee_amount']:.2f} fee")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: performance-fee.py <init|update|settle|status> <job_id> [value]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    job_id = sys.argv[2]
    
    if cmd == "init" and len(sys.argv) >= 4:
        init(job_id, sys.argv[3])
    elif cmd == "update" and len(sys.argv) >= 4:
        update(job_id, sys.argv[3])
    elif cmd == "settle" and len(sys.argv) >= 4:
        settle(job_id, sys.argv[3])
    elif cmd == "status":
        status(job_id)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
