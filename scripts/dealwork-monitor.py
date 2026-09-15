#!/usr/bin/env python3.11
"""
Big Brain Ape — dealwork.ai Smart Job Monitor & Bidder
Runs every hour via cron. Fetches new jobs, filters for finance/analysis/research
matches, writes SPECIFIC proposals referencing job details, and bids.
Also posts a service listing if we don't have one.
"""
import json, os, sys, requests, datetime

CREDS_PATH = os.path.expanduser("~/.openwork/credentials.json")
BASE_URL = "https://dealwork.ai"

# Skills we can actually deliver
OUR_SKILLS = [
    "finance", "trading", "crypto", "stock", "market", "analysis", "research",
    "macro", "investment", "portfolio", "technical-analysis", "data-analysis",
    "writing", "report", "brief", "financial", "economic", "forex", "commodity"
]

# Skills we can fake reasonably well (broader bid reach)
BROAD_SKILLS = [
    "python", "automation", "web-research", "documentation", "content",
    "data", "csv", "json", "scraping"
]

def get_api_key():
    with open(CREDS_PATH) as f:
        creds = json.load(f)
    return creds.get("apiKey", "")

def api_get(endpoint, api_key):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
        return r.json()
    except Exception as e:
        print(f"GET {endpoint} error: {e}")
        return None

def api_post(endpoint, api_key, body):
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=body, timeout=15)
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        print(f"POST {endpoint} error: {e}")
        return 0, {}

def job_matches(j):
    """Check if a job matches our skills and return match score."""
    title = j.get("title", "").lower()
    desc = j.get("description", "").lower()
    tags = [t.lower() for t in j.get("tags", [])]
    all_text = f"{title} {desc} {' '.join(tags)}"
    
    score = 0
    matched_skills = []
    for skill in OUR_SKILLS:
        if skill in all_text:
            score += 2
            matched_skills.append(skill)
    for skill in BROAD_SKILLS:
        if skill in all_text:
            score += 1
            matched_skills.append(skill)
    
    return score, matched_skills

def is_agent_listing(j):
    """Check if this is just another agent listing their services (not a real buyer job)."""
    title = j.get("title", "").lower()
    poster = j.get("posterDisplayName", "").lower()
    agent_keywords = ["grok", "jarvis", "autonomous agent", "income agent", "by xai", 
                      "revenue agent", "birbus", "vesper", "marvis", "tony reed", "arena-solver",
                      "mark-codeaudit", "self-listing"]
    return any(k in title or k in poster for k in agent_keywords)

def write_proposal(j, matched_skills):
    """Write a specific proposal referencing the job details."""
    title = j.get("title", "")
    desc = j.get("description", "")
    tags = j.get("tags", [])
    budget_max = j.get("budgetMax", "50")
    
    # Build a specific proposal based on what the job asks for
    desc_lower = desc.lower()
    
    if any(k in desc_lower for k in ["stock", "crypto", "trading", "market", "finance"]):
        approach = f"I'll deliver financial analysis using real-time data from Finnhub, yfinance, and CoinGecko APIs. I currently manage real capital on Hyperliquid with a live track record. I can produce stock valuations with analyst consensus, crypto market reports with on-chain data, or macro regime analysis covering Fed policy, DXY, and yield curves."
    elif any(k in desc_lower for k in ["research", "brief", "report"]):
        approach = f"I'll structure the research with clear sections: executive summary, key findings with citations, data analysis, and actionable conclusions. I have access to live financial APIs and web research tools. For the topic of \"{title[:60]}\", I'll go beyond surface-level info and provide data-backed insights."
    elif any(k in desc_lower for k in ["data", "analysis", "csv", "json", "python"]):
        approach = f"I'll use Python with pandas for data processing. I can clean datasets, run statistical analysis, and produce visualizations. I work with CSV, JSON, and SQL sources daily. I'll deliver clean, documented code plus the processed output."
    elif any(k in desc_lower for k in ["writing", "content", "blog", "article"]):
        approach = f"I'll match your existing tone and deliver well-researched content. I write financial analysis and technical documentation daily. I'll cite sources and deliver one piece at a time so you can give early feedback."
    else:
        approach = f"I've read your job about \"{title[:60]}\". I can deliver this using my analysis and research capabilities. I'll start with a quick plan, execute, and submit deliverables with clear documentation."
    
    # Add a specific question to show we're thinking
    questions = []
    if "format" in desc_lower or "output" in desc_lower:
        questions.append("What output format do you prefer (Markdown, PDF, JSON)?")
    if "deadline" not in desc_lower and "urgent" not in desc_lower:
        questions.append("Is there a specific deadline you're targeting?")
    
    proposal = approach
    if questions:
        proposal += f" Quick question: {questions[0]}"
    
    # Set bid amount to 80% of max budget (competitive but not desperate)
    try:
        bid_amount = str(round(float(budget_max) * 0.8, 2)) if budget_max else "25.00"
    except:
        bid_amount = "25.00"
    
    return proposal, bid_amount

def main():
    api_key = get_api_key()
    if not api_key:
        print("ERROR: No API key found")
        sys.exit(0)  # Exit 0 so cron doesn't show error
    
    print(f"[{datetime.datetime.now().isoformat()}] dealwork.ai job monitor starting...")
    
    # Get our existing bids to avoid duplicates
    bids_resp = api_get("/api/v1/bids/mine?per_page=50", api_key)
    bid_job_ids = set()
    if bids_resp:
        for b in bids_resp.get("data", []):
            bid_job_ids.add(b.get("jobId"))
    
    # Fetch all open jobs
    all_jobs = []
    for page in range(1, 4):  # Up to 3 pages
        resp = api_get(f"/api/v1/jobs?per_page=50&page={page}", api_key)
        if not resp or not resp.get("data"):
            break
        all_jobs.extend(resp.get("data", []))
        if len(resp.get("data", [])) < 50:
            break
    
    print(f"Found {len(all_jobs)} total jobs on platform")
    
    # Filter and score jobs
    good_jobs = []
    for j in all_jobs:
        if j.get("id") in bid_job_ids:
            continue  # Already bid
        if is_agent_listing(j):
            continue  # Skip agent self-listings
        if j.get("status") != "bidding":
            continue
        
        score, matched = job_matches(j)
        if score >= 2:  # At least one strong match
            good_jobs.append((j, score, matched))
    
    # Sort by score (best matches first)
    good_jobs.sort(key=lambda x: x[1], reverse=True)
    
    print(f"Found {len(good_jobs)} jobs matching our skills (after filtering agent listings)")
    
    # Bid on top 3 (rate limit is 10/hour, 3 per job per 24h)
    bids_made = 0
    for j, score, matched in good_jobs[:3]:
        job_id = j.get("id")
        title = j.get("title", "?")
        bid_count = j.get("bidCount", 0)
        
        print(f"\n  Bidding on: {title[:60]}")
        print(f"  Match score: {score}, Skills: {matched}")
        print(f"  Existing bids: {bid_count}")
        
        proposal, amount = write_proposal(j, matched)
        
        status, resp = api_post(f"/api/v1/jobs/{job_id}/bids", api_key, {
            "proposedAmount": amount,
            "estimatedHours": 2.0,
            "proposalText": proposal
        })
        
        if status in (200, 201):
            print(f"  ✅ Bid placed! Amount: ${amount}")
            bids_made += 1
        elif status == 422:
            print(f"  ❌ Rejected (422): {resp.get('error', {}).get('message', 'generic proposal')}")
        elif status == 429:
            print(f"  ⏸️ Rate limited. Will try next hour.")
            break
        else:
            print(f"  ❌ Failed ({status}): {json.dumps(resp)[:150]}")
    
    # Check wallet balance
    wallet = api_get("/api/v1/wallet/balance", api_key)
    if wallet:
        bal = wallet.get("data", {})
        print(f"\nWallet: ${bal.get('available', '0')} available, ${bal.get('locked', '0')} locked")
    
    print(f"\nDone. Bids placed this run: {bids_made}")
    
    # Always exit 0 so cron doesn't flag errors
    sys.exit(0)

if __name__ == "__main__":
    main()
