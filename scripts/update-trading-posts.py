#!/usr/bin/env python3
"""
Generates trading-posts.json from the daily trading cycle cron output files.
Reads the markdown reports from /home/hermes/.hermes/cron/output/9fd990c76ee7/,
extracts the assistant's trading report, and pushes trading-posts.json to GitHub Pages.

Silent on success.
"""
import json, os, sys, glob, time, base64, urllib.request, re
from urllib.error import HTTPError

REPO = "Simzy420/big-brain-ape-dashboard"
BRANCH = "main"
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRON_OUTPUT_DIR = "/home/hermes/.hermes/cron/output/9fd990c76ee7"

def extract_trading_report(filepath):
    """Extract the trading report content from a cron output markdown file"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # The report starts after "## Response"
        lines = content.split('\n')
        
        report_start = -1
        for i, line in enumerate(lines):
            if line.strip() == '## Response':
                report_start = i + 1
                break
        
        if report_start == -1:
            # Fallback: look for the report header pattern
            for i, line in enumerate(lines):
                if 'BIG BRAIN APE' in line and 'TRADING' in line:
                    report_start = i
                    break
        
        if report_start == -1:
            return None
        
        report_lines = lines[report_start:]
        # Clean up: remove empty lines at start/end
        while report_lines and not report_lines[0].strip():
            report_lines.pop(0)
        while report_lines and not report_lines[-1].strip():
            report_lines.pop()
        
        report_text = '\n'.join(report_lines)
        
        # Extract timestamp from filename
        basename = os.path.basename(filepath)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})', basename)
        if date_match:
            date_str = f"{date_match.group(1)} {date_match.group(2)}:{date_match.group(3)} UTC"
        else:
            date_str = basename
        
        # Extract title from first non-empty line (usually the header with ***)
        title = "Trading Report"
        for line in report_lines[:5]:
            clean = re.sub(r'[*_#]', '', line).strip()
            if len(clean) > 10:
                title = clean[:80]
                break
        
        return {
            "title": title,
            "date": date_str,
            "content": report_text,
            "file": basename
        }
    except Exception as e:
        return None

def build_trading_posts():
    """Build trading-posts.json from all cron output files"""
    files = sorted(glob.glob(os.path.join(CRON_OUTPUT_DIR, "*.md")), reverse=True)
    
    posts = []
    for filepath in files:
        post = extract_trading_report(filepath)
        if post and len(post["content"]) > 100:
            posts.append(post)
        if len(posts) >= 14:  # Keep last 7 days (2 reports/day)
            break
    
    return {
        "timestamp": int(time.time()),
        "generatedAt": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "posts": posts
    }

def push_to_github(data_json, filename="trading-posts.json"):
    """Push the generated feed to this dashboard repository."""
    env_file = "/workspace/.github.env"
    if not os.path.exists(env_file):
        print("ERROR: /workspace/.github.env not found", file=sys.stderr)
        return False

    token = None
    try:
        with open(env_file) as f:
            for line in f:
                name, separator, value = line.strip().partition("=")
                if separator and name in ("GITHUB_TOKEN", "GITHUB_TOKEN_SIMZY"):
                    token = value.strip().strip('"').strip("'")
                    if token:
                        break
    except OSError as e:
        print(f"ERROR: could not read GitHub token file: {e}", file=sys.stderr)
        return False

    if not token:
        print("ERROR: GITHUB_TOKEN is not configured in /workspace/.github.env", file=sys.stderr)
        return False

    api_url = f"https://api.github.com/repos/{REPO}/contents/{filename}"
    req = urllib.request.Request(api_url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")

    sha = None
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = json.loads(resp.read()).get("sha")
    except HTTPError as e:
        if e.code != 404:
            detail = e.read().decode("utf-8", errors="replace")[:250]
            print(f"ERROR: GitHub lookup failed (HTTP {e.code}): {detail}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"ERROR: GitHub lookup failed: {e}", file=sys.stderr)
        return False

    content = json.dumps(data_json, indent=2)
    content_b64 = base64.b64encode(content.encode()).decode()
    payload = {
        "message": f"Auto-update trading-posts.json {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode()
    req = urllib.request.Request(api_url, data=data, method="PUT")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                return True
            print(f"ERROR: GitHub write returned unexpected HTTP {resp.status}", file=sys.stderr)
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:250]
        print(f"ERROR: GitHub write failed (HTTP {e.code}): {detail}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: GitHub write failed: {e}", file=sys.stderr)
    return False

def main():
    if not os.path.exists(CRON_OUTPUT_DIR):
        print(f"FAILED: cron output dir not found: {CRON_OUTPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    posts_json = build_trading_posts()
    
    if not posts_json["posts"]:
        print("FAILED: no trading reports found in the cron output directory", file=sys.stderr)
        sys.exit(1)

    # Save locally
    local_path = os.path.join(REPO_DIR, "trading-posts.json")
    with open(local_path, "w") as f:
        json.dump(posts_json, f, indent=2)

    # Push to GitHub
    success = push_to_github(posts_json)
    if not success:
        print("FAILED: could not publish trading-posts.json; see the GitHub error above", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
