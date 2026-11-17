"""Add a new Gmail export to the message store.

    python3 ingest.py ~/Downloads/takeout-2027....zip [more.zip | All mail.mbox ...]

Accepts Google Takeout zips or bare .mbox files. Messages already in the store (same Message-ID) are
skipped, so a full re-export of the inbox only adds what is new. Rewrites work/messages.jsonl and
work/header_identities.json.
"""
import mailbox, email, email.policy, json, re, sys, os, hashlib, zipfile, tempfile, shutil, collections as C
from email.utils import parsedate_to_datetime, getaddresses
from common import data

PATS = [r'cof+e+\s*[-–]?\s*chat', r'coffe', r'interview', r'thank.?you', r'thanks', r'chatting', r'catching up',
        r'great meeting', r'nice meeting']


def key(m):
    mid = (m.get('id') or '').strip()
    if mid:
        return mid
    return 'h:' + hashlib.sha1('|'.join([m['from'], m['date'], m['subject'], m['body'][:300]]).encode()).hexdigest()


def parse(m, i):
    parts, attachments = [], []
    for p in m.walk():
        if p.is_multipart():
            continue
        ct = p.get_content_type()
        if p.get_filename():
            attachments.append({'name': p.get_filename(), 'type': ct})
        if ct in ('text/plain', 'text/html') and not p.get_filename():
            try:
                t = p.get_content()
            except Exception:
                t = (p.get_payload(decode=True) or b'').decode('utf8', 'replace')
            if isinstance(t, bytes):
                t = t.decode('utf8', 'replace')
            parts.append((ct, t))
    plain = '\n'.join(t for c, t in parts if c == 'text/plain') or '\n'.join(re.sub('<[^>]+>', ' ', t) for c, t in parts)
    try:
        d = parsedate_to_datetime(str(m.get('Date', ''))).isoformat()
    except Exception:
        d = ''
    s = str(m.get('Subject', ''))
    return {'index': i, 'id': str(m.get('Message-ID', '')), 'date': d, 'from': str(m.get('From', '')),
            'to': str(m.get('To', '')), 'cc': str(m.get('Cc', '')), 'bcc': str(m.get('Bcc', '')), 'subject': s,
            'labels': str(m.get('X-Gmail-Labels', '')), 'references': str(m.get('References', '')),
            'in_reply_to': str(m.get('In-Reply-To', '')), 'body': plain, 'attachments': attachments,
            'patterns': [p for p in PATS if re.search(p, s + '\n' + plain, re.I)]}


def mboxes(path, tmp):
    if path.endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith('.mbox'):
                    out = os.path.join(tmp, hashlib.sha1(n.encode()).hexdigest() + '.mbox')
                    with z.open(n) as src, open(out, 'wb') as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                    yield out
    elif path.endswith('.mbox'):
        yield path
    else:
        sys.exit(f'not a .zip or .mbox: {path}')


def main(paths):
    store = data('messages.jsonl')
    ms = [json.loads(l) for l in open(store)] if os.path.exists(store) else []
    seen = {key(m) for m in ms}
    added, dupes = 0, 0
    tmp = tempfile.mkdtemp(dir=data(''))
    try:
        for p in paths:
            for mb_path in mboxes(os.path.expanduser(p), tmp):
                mb = mailbox.mbox(mb_path, factory=lambda f: email.message_from_binary_file(f, policy=email.policy.default),
                                  create=False)
                for m in mb:
                    rec = parse(m, len(ms))
                    k = key(rec)
                    if k in seen:
                        dupes += 1
                        continue
                    seen.add(k)
                    ms.append(rec)
                    added += 1
                    if added % 2000 == 0:
                        print(' ', added, 'new so far', flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if added:
        with open(store + '.tmp', 'w') as f:
            for m in ms:
                f.write(json.dumps(m, ensure_ascii=False) + '\n')
        os.replace(store + '.tmp', store)
    ids = C.defaultdict(C.Counter)
    for m in ms:
        for k in ('from', 'to', 'cc'):
            for n, a in getaddresses([m[k]]):
                ids[a.lower()][n] += 1
    json.dump({a: dict(n) for a, n in ids.items()}, open(data('header_identities.json'), 'w'), indent=2)
    dates = sorted(m['date'][:10] for m in ms if m['date'])
    print(f'{added} new messages, {dupes} already stored | {len(ms)} total, {dates[0]} to {dates[-1]}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
