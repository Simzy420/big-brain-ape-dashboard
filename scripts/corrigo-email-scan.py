#!/usr/bin/env python3
"""Corrigo email scanner (replaces the old SuperGrok scanner, last run 2026-10-23).

Input: a JSON file of Gmail messages fetched by the routine through the Gmail
connector (read_email output objects: id, threadId, from, subject, date, body,
optional htmlBody), either a list or {"messages": [...]}.

Adds NEW work-order assignment emails ("The new <priority> work order #X
received from <customer>") to work-orders.json with status "inbox", using the
same fields the old scanner wrote. Skips WOs already in work-orders.json or
corrigo-overrides.json (normalized number match, incl. renames and removals),
and skips every non-assignment email (reminders, invoices, recalls, chats).

Usage:  python3 scripts/corrigo-email-scan.py emails.json [--dry-run] [--push]
Prints "NO_NEW_WOS" when nothing is added (the routine stays quiet then).
"""
import json, re, sys, subprocess, datetime, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENDERS = ('garysims60@msn.com', 'alerts@am.corrigopro.com')
ASSIGN_RE = re.compile(r'\bThe new (.+?) work order #\s*([A-Z0-9][A-Z0-9.\-]+?)\s+received from\s+(.+?)\s*$', re.I)
WO_RE = re.compile(r'\b[1IJ]\d{6,8}-\d{3,6}(?:\.\d{1,3})?\b', re.I)


def norm_strict(n):
    return re.sub(r'\s+', '', re.sub('[\u2010-\u2015\u2212]', '-', str(n or ''))).upper()


def norm_wo(n):  # same rule as the app's normWo()
    return re.sub(r'^[1IJ](?=\d)', '*', norm_strict(n))


def field(body, label, multiline_next=False):
    """Value after 'Label:' on the same line, or on the next non-empty line."""
    m = re.search(r'^\s*' + re.escape(label) + r':?[ \t]*(.*)$', body, re.M | re.I)
    if not m:
        return None
    v = m.group(1).strip()
    if v or not multiline_next:
        return v or None
    rest = body[m.end():].lstrip('\r\n')
    for line in rest.splitlines():
        if line.strip():
            return line.strip()
    return None


def parse(msg):
    body = (msg.get('body') or '').replace('\r\n', '\n')
    subj = msg.get('subject') or ''
    sm = ASSIGN_RE.search(subj)
    num = sm.group(2).rstrip('.') if sm else None
    m = re.search(r'WORK ORDER #\s*(\S+)', body)
    if m and not num:
        num = m.group(1)
    # Date Created: the label line carries the NTE banner; the date is on the next line.
    created = None
    m = re.search(r'Date Created:[^\n]*\n\s*(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2} [AP]M)', body)
    if m:
        created = m.group(1)
    banner = field(body, 'Date Created')
    nte = None
    m = re.search(r'NTE:\s*\$([\d,]+(?:\.\d+)?)', body) or re.search(r'DO NOT EXCEED[^$]*\$([\d,]+(?:\.\d+)?)', body)
    if m:
        nte = float(m.group(1).replace(',', ''))
    problem = None
    m = re.search(r'\nProblem\n(.*?)\nDetails\n', body, re.S)
    if m:
        problem = m.group(1).strip('\n')
    m = re.search(r'Expanded Work Description:\s*(.*?)\n\s*\n', body, re.S)
    expanded = m.group(1).strip() if m else None
    req = field(body, 'Requested By')
    mt = re.search(r'Customer\n_+\nName:\s*(.+)', body)
    return {
        'number': num,
        'estimatedAmount': nte,
        'location': field(body, 'Site Address'),
        'requestedBy': req,
        'serviceContact': field(body, 'Service Contact Manager'),
        'ivrCode': field(body, 'IVR code'),
        'description': ('_' * 32 + '\n' + problem) if problem and not problem.startswith('_') else problem,
        'workDescription': expanded,
        'priority': field(body, 'Priority', True),
        'onSiteBy': field(body, 'On-Site By', True),
        'completeBy': field(body, 'Complete By', True),
        'acceptBy': field(body, 'Accept/Reject By', True),
        'dateCreated': created,
        'property': field(body, 'Property'),
        'customer': (mt.group(1).strip() if mt else (sm.group(3).strip() if sm else None)),
        'date': banner,  # old scanner stored the text beside "Date Created:" here
        'type': field(body, 'Type', True),
        'status': 'inbox',
        'bidAmount': None,
        'completedSummary': None,
        'photo': None,
        'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(),
        'id': 'wo_real_' + re.sub(r'[^A-Za-z0-9]', '_', num or ''),
        'gmailMsgId': msg.get('id'),
        'gmailThreadId': msg.get('threadId'),
        'emailSubject': subj,
        'emailContent': msg.get('body') or '',
        'emailHtml': msg.get('htmlBody') or '',
        'corrigoUrl': None,
    }


def known_numbers():
    known, removed = set(), set()
    wos = json.load(open(os.path.join(REPO, 'work-orders.json')))
    for w in wos:
        for k in ('number', 'corrigoWoNumber'):
            if w.get(k):
                known.add(norm_wo(w[k]))
    try:
        ov = json.load(open(os.path.join(REPO, 'corrigo-overrides.json')))
        ov = ov.get('overrides', ov) if isinstance(ov, dict) else ov
    except FileNotFoundError:
        ov = []
    for o in ov:
        for n in (o.get('number'), o.get('renameTo'), (o.get('wo') or {}).get('number')):
            if n:
                known.add(norm_wo(n))
                if o.get('removed'):
                    removed.add(norm_wo(n))
    return wos, known, removed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry, push = '--dry-run' in sys.argv, '--push' in sys.argv
    data = json.load(open(args[0]))
    msgs = data.get('messages', data) if isinstance(data, dict) else data
    wos, known, removed = known_numbers()
    msgs = sorted(msgs, key=lambda m: m.get('date') or '')
    added, notes = [], []
    for msg in msgs:
        subj = msg.get('subject') or ''
        frm = (msg.get('from') or '').lower()
        body = msg.get('body') or ''
        if not any(s in frm for s in SENDERS) or 'alerts@am.corrigopro.com' not in body + frm:
            continue
        if not ASSIGN_RE.search(subj):
            nums = WO_RE.findall(subj)
            if nums and re.search(r'waiting for your arrival|will be overdue', subj, re.I) \
                    and norm_wo(nums[0]) not in known:
                notes.append('reminder for unknown WO %s (not added; no assignment email)' % nums[0])
            continue
        row = parse(msg)
        n = row['number']
        if not n or not WO_RE.fullmatch(n):
            notes.append('could not read WO number from: ' + subj)
            continue
        k = norm_wo(n)
        if k in removed or k in known:
            continue
        known.add(k)
        added.append(row)
    for n in notes:
        print('NOTE:', n)
    if not added:
        print('NO_NEW_WOS')
        return
    for r in added:
        print('NEW: %s | %s | %s | NTE %s | on-site by %s' % (r['number'], r['property'] or r['requestedBy'],
              r['location'], r['estimatedAmount'], r['onSiteBy']))
    if dry:
        print('DRY_RUN: %d new WO(s), nothing written' % len(added))
        return
    path = os.path.join(REPO, 'work-orders.json')
    json.dump(wos + added, open(path, 'w'), indent=2, ensure_ascii=False)
    g = ['git', '-C', REPO]
    ident = ['-c', 'user.name=Big Brain Ape 🧠 👑', '-c', 'user.email=big.brain.ape.trading.bot@gmail.com']
    subprocess.run(g + ['add', 'work-orders.json'], check=True)
    subprocess.run(g + ident + ['commit', '-qm', 'Auto-update work orders %s: add %s' % (
        datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M'), ', '.join(r['number'] for r in added))], check=True)
    if push:
        subprocess.run(g + ident + ['pull', '-q', '--rebase'], check=True)
        subprocess.run(g + ['push', '-q'], check=True)
    print('ADDED: %d' % len(added))


if __name__ == '__main__':
    main()
