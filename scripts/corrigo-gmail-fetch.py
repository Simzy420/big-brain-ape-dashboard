#!/usr/bin/env python3
"""Fetch Gary/Corrigo Gmail messages via Composio → emails.json for corrigo-email-scan.py.

Uses Composio REST execute (GMAIL_FETCH_EMAILS / GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID).
Does not invent duplicates; scanner still owns WO idempotency against work-orders.json
and corrigo-overrides.json.

Env (required for live fetch):
  COMPOSIO_API_KEY
Optional:
  COMPOSIO_CONNECTED_ACCOUNT_ID  (pin Casey's Gmail ca_…; recommended)
  COMPOSIO_USER_ID               (multi-user projects; often email or 'default')
  COMPOSIO_BASE_URL              (default https://backend.composio.dev/api/v3)
  COMPOSIO_TOOLKIT_VERSION       (default latest)

Usage:
  python3 scripts/corrigo-gmail-fetch.py [-o /tmp/emails.json]
      [--query 'from:garysims60@msn.com …'] [--max-results 50] [--newer-than 3d]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_QUERY = (
    'from:garysims60@msn.com '
    '(corrigopro OR "work order" OR alerts@am.corrigopro.com)'
)
DEFAULT_BASE = 'https://backend.composio.dev/api/v3'
ASSIGN_HINT = re.compile(
    r'\bThe new .+? work order #\s*[A-Z0-9].+?\s+received from\b', re.I
)
PAID_HINT = re.compile(
    r'\b(?:has been paid|payment (?:has been )?(?:received|issued|processed|made)|'
    r'invoice\b.{0,40}\bpaid)\b',
    re.I,
)


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def api_key() -> str:
    key = (os.environ.get('COMPOSIO_API_KEY') or '').strip()
    if not key:
        die('COMPOSIO_API_KEY is required (GitHub Actions secret or local env).')
    return key


def base_url() -> str:
    return (os.environ.get('COMPOSIO_BASE_URL') or DEFAULT_BASE).rstrip('/')


def execute(slug: str, arguments: dict[str, Any]) -> Any:
    """POST /tools/execute/{slug}; return data.data or data."""
    body: dict[str, Any] = {
        'arguments': arguments,
        'version': os.environ.get('COMPOSIO_TOOLKIT_VERSION') or 'latest',
    }
    ca = (os.environ.get('COMPOSIO_CONNECTED_ACCOUNT_ID') or '').strip()
    if ca:
        body['connected_account_id'] = ca
    uid = (os.environ.get('COMPOSIO_USER_ID') or '').strip()
    if uid:
        body['user_id'] = uid

    req = urllib.request.Request(
        f'{base_url()}/tools/execute/{slug}',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-api-key': api_key(),
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')
        die(f'Composio {slug} HTTP {e.code}: {detail[:2000]}')
    except urllib.error.URLError as e:
        die(f'Composio {slug} network error: {e}')

    if isinstance(payload, dict):
        if payload.get('successful') is False or payload.get('error'):
            die(f'Composio {slug} failed: {payload.get("error") or payload}')
        data = payload.get('data', payload)
        # Nested execute wrappers
        if isinstance(data, dict) and 'data' in data and (
            'successful' in data or 'response_data' in data or 'messages' in data.get('data', {})
        ):
            inner = data.get('data')
            if isinstance(inner, (dict, list)):
                return inner
        if isinstance(data, dict) and 'response_data' in data:
            return data['response_data']
        return data
    return payload


def b64url_decode(s: str) -> str:
    if not s:
        return ''
    pad = '=' * (-len(s) % 4)
    raw = base64.urlsafe_b64decode((s + pad).encode('ascii'))
    for enc in ('utf-8', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def walk_parts(part: Any, plain: list[str], html: list[str]) -> None:
    if not isinstance(part, dict):
        return
    mime = (part.get('mimeType') or '').lower()
    body = part.get('body') or {}
    data = body.get('data')
    if data and mime == 'text/plain':
        plain.append(b64url_decode(data))
    elif data and mime == 'text/html':
        html.append(b64url_decode(data))
    for child in part.get('parts') or []:
        walk_parts(child, plain, html)


def header_map(payload: dict) -> dict[str, str]:
    headers = {}
    for h in (payload.get('headers') or []):
        if isinstance(h, dict) and h.get('name'):
            headers[h['name'].lower()] = h.get('value') or ''
    return headers


def extract_bodies(msg: dict) -> tuple[str, str]:
    """Return (plain, html) from Composio/Gmail-shaped message objects."""
    # Already-normalized connector shapes
    if msg.get('body') or msg.get('htmlBody') or msg.get('messageText'):
        plain = msg.get('body') or msg.get('messageText') or msg.get('text') or ''
        html = msg.get('htmlBody') or msg.get('messageHtml') or msg.get('html') or ''
        return str(plain), str(html)

    payload = msg.get('payload')
    if isinstance(payload, dict):
        plain, html = [], []
        walk_parts(payload, plain, html)
        if plain or html:
            return '\n'.join(plain), '\n'.join(html)

    # Composio sometimes flattens
    for key in ('message', 'data', 'email'):
        nested = msg.get(key)
        if isinstance(nested, dict):
            return extract_bodies(nested)
    return '', ''


def normalize_message(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    # Unwrap common envelopes
    for key in ('message', 'data', 'email'):
        if key in raw and isinstance(raw[key], dict) and (
            raw[key].get('id') or raw[key].get('messageId') or raw[key].get('message_id')
        ):
            raw = {**raw, **raw[key]}

    mid = raw.get('id') or raw.get('messageId') or raw.get('message_id')
    if not mid:
        return None
    tid = raw.get('threadId') or raw.get('thread_id') or mid
    payload = raw.get('payload') if isinstance(raw.get('payload'), dict) else {}
    headers = header_map(payload) if payload else {}
    # Prefer top-level fields Composio may already decode
    frm = (
        raw.get('from') or raw.get('sender') or raw.get('from_email')
        or headers.get('from') or ''
    )
    subj = raw.get('subject') or headers.get('subject') or ''
    date = (
        raw.get('date') or raw.get('messageTimestamp') or raw.get('internalDate')
        or headers.get('date') or ''
    )
    if isinstance(date, (int, float)):
        # Gmail internalDate is ms since epoch
        import datetime
        ms = int(date)
        if ms > 10_000_000_000:  # ms
            ms //= 1000
        date = datetime.datetime.utcfromtimestamp(ms).isoformat() + 'Z'

    body, html = extract_bodies(raw)
    preview = raw.get('preview') or raw.get('snippet') or ''
    if not body and preview:
        body = str(preview)

    return {
        'id': str(mid),
        'threadId': str(tid),
        'from': str(frm),
        'subject': str(subj),
        'date': str(date),
        'body': body,
        'htmlBody': html,
    }


def collect_message_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ('messages', 'data', 'items', 'emails', 'response_data'):
        v = data.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ('messages', 'data', 'items'):
                if isinstance(v.get(k2), list):
                    return v[k2]
    # Single message
    if data.get('id') or data.get('messageId'):
        return [data]
    return []


def needs_full_body(msg: dict) -> bool:
    subj = msg.get('subject') or ''
    body = msg.get('body') or ''
    if len(body) >= 200 and 'alerts@am.corrigopro.com' in (body + (msg.get('from') or '')).lower():
        return False
    if ASSIGN_HINT.search(subj) or PAID_HINT.search(subj):
        return True
    return False


def fetch_full(message_id: str) -> dict[str, Any] | None:
    data = execute(
        'GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID',
        {'message_id': message_id, 'format': 'full', 'user_id': 'me'},
    )
    # Response may nest under message/data
    if isinstance(data, dict) and 'message' in data:
        return normalize_message(data['message'] if isinstance(data['message'], dict) else data)
    return normalize_message(data if isinstance(data, dict) else {'data': data})


def fetch_page(query: str, max_results: int, page_token: str | None) -> tuple[list[dict], str | None]:
    args: dict[str, Any] = {
        'query': query,
        'max_results': max_results,
        'include_payload': True,
        'verbose': True,
        'user_id': 'me',
        'ids_only': False,
    }
    if page_token:
        args['page_token'] = page_token
    data = execute('GMAIL_FETCH_EMAILS', args)
    msgs = []
    seen = set()
    for raw in collect_message_list(data):
        norm = normalize_message(raw)
        if not norm or norm['id'] in seen:
            continue
        seen.add(norm['id'])
        if needs_full_body(norm):
            full = fetch_full(norm['id'])
            if full and (full.get('body') or full.get('htmlBody')):
                # Keep list metadata if full fetch omitted them
                for k in ('from', 'subject', 'date', 'threadId'):
                    if not full.get(k) and norm.get(k):
                        full[k] = norm[k]
                norm = full
        msgs.append(norm)
    next_token = None
    if isinstance(data, dict):
        next_token = data.get('nextPageToken') or data.get('next_page_token')
        if not next_token and isinstance(data.get('data'), dict):
            next_token = data['data'].get('nextPageToken') or data['data'].get('next_page_token')
    return msgs, next_token


def build_query(base: str, newer_than: str | None) -> str:
    q = base.strip()
    if newer_than:
        # Gmail relative operator
        q = f'{q} newer_than:{newer_than.lstrip(":")}'
    return q


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('-o', '--output', default='emails.json')
    ap.add_argument('--query', default=DEFAULT_QUERY)
    ap.add_argument('--max-results', type=int, default=40)
    ap.add_argument('--newer-than', default='3d',
                    help='Gmail newer_than: window (default 3d). Pass empty to disable.')
    ap.add_argument('--pages', type=int, default=1,
                    help='Max list pages to pull (default 1 for speed).')
    args = ap.parse_args()

    newer = args.newer_than.strip() if args.newer_than is not None else ''
    query = build_query(args.query, newer or None)
    print(f'QUERY: {query}', file=sys.stderr)

    all_msgs: list[dict] = []
    seen: set[str] = set()
    token = None
    for page in range(max(1, args.pages)):
        batch, token = fetch_page(query, min(max(1, args.max_results), 500), token)
        for m in batch:
            if m['id'] in seen:
                continue
            seen.add(m['id'])
            all_msgs.append(m)
        if not token:
            break
        print(f'PAGE {page + 1}: {len(batch)} msgs, continuing…', file=sys.stderr)

    out = {'messages': all_msgs}
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f'WROTE {len(all_msgs)} messages → {args.output}')


if __name__ == '__main__':
    main()
