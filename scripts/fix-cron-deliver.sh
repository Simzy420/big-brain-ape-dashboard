#!/bin/bash
# Force ALL cron jobs to deliver=local (silent) — runs every minute
python3.11 -c "
import json, os, fcntl

JOBS_FILE = '/home/hermes/.hermes/cron/jobs.json'

try:
    with open(JOBS_FILE, 'r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        data = json.load(f)
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    changed = False
    for job in data.get('jobs', []):
        if job.get('deliver') != 'local':
            job['deliver'] = 'local'
            changed = True
    
    if changed:
        with open(JOBS_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
except Exception as e:
    pass
" 2>/dev/null
