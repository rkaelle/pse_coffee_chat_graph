"""Turn raw notes into a clean chat table with canonical people, chat type, cohorts and flags."""
import json, re, sys, collections as C, datetime as dt, unicodedata
from common import data, COHORT_SEM
R = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
roster = json.load(open(data('roster.json')))
hdr = json.load(open(data('header_identities.json')))
addr_map = json.load(open(data('address_map.json')))

def sem(d):
    y, m = int(d[:4]), int(d[5:7])
    return ('W' if m <= 6 else 'F') + str(y)[2:]

def semkey(s):
    return int(s[1:]) * 2 + (s[0] == 'F')

def name_for(addr, shown):
    if addr in addr_map:
        return addr_map[addr]
    opts = C.Counter({k: v for k, v in hdr.get(addr, {}).items() if k.strip()})
    if shown.strip() and '@' not in shown:
        opts[shown.strip()] += 1
    return opts.most_common(1)[0][0] if opts else ''

def clean_name(n):
    return re.sub(r'\s+', ' ', n.strip('"\' ')).strip()

def norm(n):
    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z ]', '', n)

EXCL = re.compile(r"(?i)workshop|panel|speaker|info(rmation)? ?session|\bevent\b|apolog|absen|self.?reflection|feedback|"
                  r"weather report|reaching out|conflict|strike|essay|podcast|consulting (project|meeting)|project thank|"
                  r"\bchapter\b|introduction|recruit|career fair|networking|office hours|presentation|rush|mock interview|"
                  r"internship interview|meet the|fireside|luncheon|dinner|trek|case comp")
CHAT = re.compile(r"(?i)coff?e|chat|interview|\bcall\b|meeting|thank|facetime|zoom|talk")

rows = []
for r in R:
    s, t = r['saddr'], r['taddr']
    sn, tn = clean_name(name_for(s, r['sender'])), clean_name(name_for(t, r['target']))
    subj = r['subject'] or ''
    body = r['body']
    b0 = body[:450]
    if EXCL.search(subj) and not re.search(r'(?i)coff?e chat|pse interview', subj):
        continue
    if not CHAT.search(subj + ' ' + b0):
        continue
    if re.search(r'(?i)^.{0,200}(attending|speak(ing)? at|at the .{0,30}(event|session|panel))', b0.replace('\n', ' ')) and 'coffee' not in subj.lower():
        continue
    internal = t.endswith('umich.edu') or t in addr_map
    low = (subj + ' ' + b0).lower()
    if re.search(r'mentor', subj.lower()):
        ctype = 'mentor'
    elif re.search(r'alum', low):
        ctype = 'alumni'
    elif not internal:
        ctype = 'external'
    elif re.search(r'(?i)resume|cover letter', subj):
        ctype = 'resume'
    else:
        ctype = 'chat'
    rows.append(dict(idx=r['idx'], ts=r['date'], date=r['date'][:10], sem=sem(r['date']), s=sn or s, saddr=s, t=tn or t, taddr=t,
                     subject=subj, body=body, type=ctype, forwarded=r['forwarded']))

# dedupe: same sender and target with identical text, or within one day
rows.sort(key=lambda x: x['ts'])
seen, out = {}, []
for x in rows:
    key = (x['saddr'], x['taddr'])
    k2 = re.sub(r'\W+', '', x['body'].lower())[:200]
    if any(p['k2'] == k2 or abs((dt.date.fromisoformat(x['date']) - dt.date.fromisoformat(p['date'])).days) <= 1 for p in seen.get(key, [])):
        continue
    seen.setdefault(key, []).append(dict(k2=k2, date=x['date']))
    out.append(x)

# merge split identities by normalised full name, then prefer roster names by address
canon = {}
for x in out:
    for f in ('s', 't'):
        canon.setdefault(norm(x[f]), C.Counter())[x[f]] += 1
for x in out:
    for f in ('s', 't'):
        x[f] = canon[norm(x[f])].most_common(1)[0][0]
by_addr = C.defaultdict(C.Counter)
for x in out:
    by_addr[x['saddr']][x['s']] += 1
    by_addr[x['taddr']][x['t']] += 1
for x in out:
    x['s'] = next((n for n, v in roster.items() if v.get('email') == x['saddr']), by_addr[x['saddr']].most_common(1)[0][0])
    x['t'] = next((n for n, v in roster.items() if v.get('email') == x['taddr']), by_addr[x['taddr']].most_common(1)[0][0])

# cohort: roster first, else the semester they were sending quota-level volume
vol = C.Counter((x['s'], x['sem']) for x in out)
first = {}
for (p, s), n in vol.items():
    if n >= 6 and (p not in first or semkey(s) < semkey(first[p])):
        first[p] = s
def cohort(p):
    if p in roster and roster[p]['cohort'] in COHORT_SEM:
        return COHORT_SEM[roster[p]['cohort']]
    if p in roster:
        return 'EX'
    return first.get(p, '')
for x in out:
    x['sc'], x['tc'] = cohort(x['s']), cohort(x['t'])

json.dump(out, open(OUT, 'w'))
print(len(out), 'clean notes')
