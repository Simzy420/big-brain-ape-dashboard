#!/usr/bin/env python3
"""Gary Corrigo forward → app Inbox sync (fetch + scan).

Fast durable path for GitHub Actions (poll) or local ops:
  1) corrigo-gmail-fetch.py  → emails.json (Composio Gmail)
  2) corrigo-email-scan.py   → updates work-orders.json

Idempotency: corrigo-email-scan.py skips any WO already present in
work-orders.json or corrigo-overrides.json (normalized number, renames,
removed). This wrapper never bypasses that logic.

Usage:
  python3 scripts/corrigo-inbox-sync.py [--dry-run] [--push]
      [--newer-than 3d] [--max-results 40]

Exit codes: 0 on success (including NO_NEW_WOS); non-zero on fetch/scan failure.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FETCH = os.path.join(REPO, 'scripts', 'corrigo-gmail-fetch.py')
SCAN = os.path.join(REPO, 'scripts', 'corrigo-email-scan.py')


def run(cmd: list[str]) -> int:
    print('+', ' '.join(cmd), flush=True)
    p = subprocess.run(cmd)
    return p.returncode


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--push', action='store_true',
                    help='Commit and push work-orders.json when the scanner adds/updates rows.')
    ap.add_argument('--newer-than', default='3d')
    ap.add_argument('--max-results', type=int, default=40)
    ap.add_argument('--query', default=None)
    ap.add_argument('--emails-json', default=None,
                    help='Skip fetch; scan this emails.json instead (testing).')
    args = ap.parse_args()

    if args.push and args.dry_run:
        print('Refuse --push with --dry-run', file=sys.stderr)
        raise SystemExit(2)

    with tempfile.TemporaryDirectory(prefix='corrigo-inbox-') as td:
        emails = args.emails_json or os.path.join(td, 'emails.json')
        if not args.emails_json:
            fetch_cmd = [
                sys.executable, FETCH, '-o', emails,
                '--newer-than', args.newer_than,
                '--max-results', str(args.max_results),
            ]
            if args.query:
                fetch_cmd.extend(['--query', args.query])
            rc = run(fetch_cmd)
            if rc != 0:
                raise SystemExit(rc)

        scan_cmd = [sys.executable, SCAN, emails]
        if args.dry_run:
            scan_cmd.append('--dry-run')
        if args.push:
            scan_cmd.append('--push')
        rc = run(scan_cmd)
        raise SystemExit(rc)


if __name__ == '__main__':
    main()
