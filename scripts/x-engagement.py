#!/usr/bin/env python3
"""
X/Twitter Engagement Bot — replies to 3 posts/day about stocks/crypto/AI.
Finds posts <3 hours old with 5-50 replies, writes helpful replies.
Runs as a single cron job alongside the daily market snapshot.
"""
import json, subprocess, sys, os, re, time
from datetime import datetime, timezone, timedelta
import yaml

# ===== CONFIG =====
XURL = "/home/hermes/.hermes/home/.local/bin/xurl"
AUTH_FILE = "/home/hermes/.hermes/home/.xurl/auth.yml"
STATE_FILE = os.path.expanduser("~/.hermes/cron/x-engagement-state.json")
MAX_REPLIES_PER_DAY = 3
MAX_AGE_HOURS = 3
MIN_REPLIES = 5
MAX_REPLIES_FILTER = 50

def load_oauth1():
    with open(AUTH_FILE) as f:
        d = yaml.safe_load(f)
    app = d.get('apps', {}).get('default', {})
    oauth1 = app.get('oauth1_token', {}).get('oauth1', {})
    return {
        'consumer_key': oauth1.get('consumer_key'),
        'consumer_secret': oauth1.get('consumer_secret'),
        'access_token': oauth1.get('access_token'),
        'token_secret': oauth1.get('token_secret'),
    }

def search_tweets_oauth1(creds, query, max_results=50):
    from requests_oauthlib import OAuth1Session
    oauth = OAuth1Session(
        creds['consumer_key'],
        client_secret=creds['consumer_secret'],
        resource_owner_key=creds['access_token'],
        resource_owner_secret=creds['token_secret'],
    )
    params = {
        'query': query,
        'max_results': max_results,
        'tweet.fields': 'created_at,public_metrics,author_id',
    }
    resp = oauth.get('https://api.x.com/2/tweets/search/recent', params=params)
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get('data', [])

def reply_to_tweet(tweet_id, text):
    result = subprocess.run(
        [XURL, '--auth', 'oauth1', 'reply', str(tweet_id), text],
        capture_output=True, text=True, timeout=30
    )
    out = result.stdout.strip()
    try:
        if '{' in out:
            return json.loads(out[out.index('{'):])
        return {"error": out[:200]}
    except:
        return {"error": out[:200]}

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"replied_today": [], "last_date": ""}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def filter_tweets(tweets):
    now = datetime.now(timezone.utc)
    filtered = []
    for t in tweets:
        m = t.get('public_metrics', {})
        replies = m.get('reply_count', 0)
        try:
            dt = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
            age_hours = (now - dt).total_seconds() / 3600
        except:
            continue
        # Skip retweets (text starts with RT @)
        if t.get('text', '').startswith('RT @'):
            continue
        if age_hours <= MAX_AGE_HOURS and MIN_REPLIES <= replies <= MAX_REPLIES_FILTER:
            t['age_hours'] = age_hours
            filtered.append(t)
    return filtered

def is_on_topic(text):
    """Check if tweet is actually about stocks/crypto/AI/finance."""
    t = text.lower()
    finance_words = [
        'stock', 'stocks', 'sp500', 's&p', 'nasdaq', 'dow', 'spy', 'qqq',
        'nvda', 'amd', 'aapl', 'tsla', 'msft', 'googl', 'meta', 'earnings',
        'fed', 'rate', 'powell', 'jackson hole', 'treasury', 'bond', 'yield',
        'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'altcoin', 'defi',
        'solana', 'sol', 'liquidation', 'market cap', 'bullish', 'bearish',
        'portfolio', 'trading', 'investor', 'investing', 'dividend',
        'ai stock', 'ai invest', 'ai bubble', 'chip', 'semiconductor',
        'nvidia', 'leverage', 'long', 'short', 'call', 'put', 'option',
        'etf', 'index', 'commodity', 'gold', 'oil', 'dollar', 'forex',
    ]
    return any(w in t for w in finance_words)

def generate_reply(tweet_text):
    text_lower = tweet_text.lower()
    
    # Stock-related
    if any(w in text_lower for w in ['stock', 'sp500', 's&p', 'nasdaq', 'dow', 'spy', 'qqq', 'nvda', 'amd', 'aapl', 'tsla', 'msft', 'earnings', 'fed', 'rate', 'jackson hole', 'powell', 'treasury', 'bond']):
        if 'earnings' in text_lower:
            return "Earnings season separates the wheat from the chaff. Look at revenue growth + forward guidance, not just the EPS beat. The market trades on what's ahead."
        if 'crash' in text_lower or 'dump' in text_lower or 'sell off' in text_lower or 'liquidat' in text_lower:
            return "Volatility creates opportunity. The best setups come when fear is highest. Focus on support levels and volume — that's where smart money leaves footprints."
        if 'fed' in text_lower or 'rate' in text_lower or 'powell' in text_lower or 'jackson' in text_lower:
            return "Liquidity drives markets more than earnings ever will. Watch what the Fed does, not what they say. The bond market always tells the truth first."
        if 'buy' in text_lower or 'bullish' in text_lower:
            return "Position sizing matters more than direction. Scale in, let the market confirm your thesis. The best traders are patient hunters."
        return "Price action tells the truth. Fundamentals set direction, technicals tell you WHEN. Always check the chart before committing capital."

    # Crypto
    if any(w in text_lower for w in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'altcoin', 'defi', 'solana', 'sol', 'liquidat']):
        if 'crash' in text_lower or 'dump' in text_lower or 'bear' in text_lower or 'liquidat' in text_lower:
            return "Crypto moves in cycles. The brutal drawdowns test conviction. DCA into fear has historically been the highest-EV strategy."
        if 'bull' in text_lower or 'pump' in text_lower or 'moon' in text_lower or 'surge' in text_lower:
            return "Euphoria phases are for taking profits, not adding risk. The crowd is loudest at the top. Stick to your plan."
        if 'bitcoin' in text_lower or 'btc' in text_lower:
            return "BTC's correlation with global liquidity is the real signal. Watch the Fed, M2, stablecoin inflows. Those tell you where price goes next."
        return "In crypto, fundamentals = tokenomics + adoption + liquidity flow. If you're not tracking on-chain data, you're trading blind."

    # AI
    if any(w in text_lower for w in ['ai', 'artificial intelligence', 'machine learning', 'gpt', 'llm', 'nvidia', 'chip', 'semiconductor']):
        return "The AI buildout is the most consequential capex cycle since the internet. But valuation discipline matters — the market prices in even the best stories eventually."

    return "Markets reward patience and punish emotion. Have a thesis, size your position, define your exit before you enter. The edge is in process, not prediction."

def main():
    print(f"=== X Engagement Bot — {datetime.now(timezone.utc).isoformat()} ===")
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    state = load_state()
    
    if state.get('last_date') != today:
        state['replied_today'] = []
        state['last_date'] = today
        save_state(state)
    
    remaining = MAX_REPLIES_PER_DAY - len(state.get('replied_today', []))
    if remaining <= 0:
        print(f"Already replied to {MAX_REPLIES_PER_DAY} posts today. Done.")
        return
    
    print(f"Need to reply to {remaining} more posts today.")
    
    creds = load_oauth1()
    
    # Use targeted queries that find engaged posts
    queries = [
        "bitcoin crash OR bitcoin surge OR bitcoin liquidation",
        "stocks sell off OR stocks rally OR market crash",
        "crypto crash OR crypto surge OR crypto liquidation",
        "NVDA earnings OR NVIDIA stock",
        "Fed rate cut OR Powell OR Jackson Hole",
        "AI stocks OR AI bubble OR AI investing",
        "stock market today",
        "crypto market today",
    ]
    
    all_candidates = []
    seen_ids = set()
    
    for q in queries:
        print(f"\nSearching: {q}")
        tweets = search_tweets_oauth1(creds, q, max_results=50)
        print(f"  Got {len(tweets)} raw tweets")
        
        filtered = filter_tweets(tweets)
        print(f"  After filtering (<{MAX_AGE_HOURS}h, {MIN_REPLIES}-{MAX_REPLIES_FILTER} replies): {len(filtered)} tweets")
        
        for t in filtered:
            if t['id'] not in seen_ids:
                seen_ids.add(t['id'])
                all_candidates.append(t)
        
        if len(all_candidates) >= 15:
            break  # Enough candidates
    
    # Sort by reply count descending
    all_candidates.sort(key=lambda x: x.get('public_metrics', {}).get('reply_count', 0), reverse=True)
    
    print(f"\nTotal unique candidates: {len(all_candidates)}")
    
    if not all_candidates:
        print("No suitable tweets found. Will try again next run.")
        return
    
    # Reply to up to 'remaining' posts
    replied = 0
    for tweet in all_candidates:
        if replied >= remaining:
            break
        
        tweet_id = tweet['id']
        if tweet_id in state.get('replied_today', []):
            continue
        
        tweet_text = tweet.get('text', '')
        
        # Skip if not actually about finance/crypto/AI
        if not is_on_topic(tweet_text):
            print(f"\n  Skipping (off-topic): {tweet_text[:60]}...")
            continue
        
        reply_text = generate_reply(tweet_text)
        
        if len(reply_text) > 280:
            reply_text = reply_text[:277] + "..."
        
        print(f"\n  Replying to tweet ID: {tweet_id}")
        print(f"  Original: {tweet_text[:80]}...")
        print(f"  Reply: {reply_text}")
        
        result = reply_to_tweet(tweet_id, reply_text)
        if 'error' in result:
            print(f"  ❌ Reply failed: {result.get('error')}")
        else:
            print(f"  ✅ Reply posted!")
            replied += 1
        
        state['replied_today'].append(tweet_id)
        save_state(state)
        
        if replied < remaining:
            time.sleep(8)
    
    print(f"\n=== Done. Replied to {replied} posts. Total today: {len(state.get('replied_today', []))} ===")

if __name__ == "__main__":
    main()
