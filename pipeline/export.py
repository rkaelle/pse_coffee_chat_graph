"""Apply the deck's scope rules to the clean chats and write the graph data the site loads."""
import json, os, re, sys, datetime as dt, collections as C
from common import data, PRIVATE, SEM_TO_CLASS as CL, COHORT_SHORT as COH, CFG, overrides
roster = json.load(open(data('roster.json')))
X = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
OV = overrides()
ch = [x for x in X if x['type'] in ('chat', 'mentor', 'resume') and x['sem'] in CL and x['sc'] != 'EX']
NOT = re.compile(r"(?i)tardy|personal development|professional development|\bPD \d|unprofessional|q&a|kahoot|early departure|for speaking|speaking to us|mckinsey|mizuho|company visit|shadowing|interested in consulting|body language|thank you 03/15|for your help 02/19|FTI phone")
LEAD = re.compile(r"(?i)\b(lead(ing)?|teach(ing)? us|sit in on|presenting|your presentation|your workshop)\b")
ch = [x for x in ch if not NOT.search(x['subject']) and not (not re.search(r'(?i)coff?e|chat', x['subject']) and LEAD.search(x['body'][:260]))]
# scope: current members plus recent graduates only (no one who was already a brother or new member in 2020-21)
OLD = {p for x in X if x['sem'] in CFG['out_of_scope_semesters'] and x['type'] in ('chat', 'mentor', 'resume')
       for p in (x['s'], x['t'])}  # brothers then, or new members then: either way long-graduated alumni now
DROPPED = {x['t'] for x in ch if x['t'] not in roster and x['t'] in OLD}
ch = [x for x in ch if x['s'] in roster and x['t'] not in DROPPED]
# chats known only from screenshots (private/overrides.json); dropped once the real email is in an export
def sem_of(d):
    return ('W' if int(d[5:7]) <= 6 else 'F') + d[2:4]
have = C.defaultdict(list)
for x in ch:
    have[(x['s'], x['t'])].append(dt.date.fromisoformat(x['date']))
manual_used = 0
for a, b, d, *_ in OV['manual_chats']:
    if any(abs((dt.date.fromisoformat(d) - e).days) <= 4 for e in have[(a, b)]):
        continue
    ch.append(dict(s=a, t=b, date=d, sem=sem_of(d)))
    manual_used += 1

# a few people only ever appear by email address; publish a name, never the address
for x in ch:
    x['s'], x['t'] = OV['name_fix'].get(x['s'], x['s']), OV['name_fix'].get(x['t'], x['t'])
people = sorted({x['s'] for x in ch} | {x['t'] for x in ch})

# The public site shows first name and last initial. The full names stay in private/names.json
# (never deployed), and `python3 export.py chats.json out.json --full-names` publishes them instead.
LAST = OV['last_name']
def short_names(full):
    parts = {p: (p.split()[0], LAST.get(p, p.split()[-1]).rstrip('.')) for p in full}
    n = {p: 1 for p in full}
    while True:
        out = {p: f'{f} {l[:n[p]]}.' for p, (f, l) in parts.items()}
        clash = [p for p in full if list(out.values()).count(out[p]) > 1 and n[p] < len(parts[p][1])]
        if not clash:
            return out
        for p in clash:
            n[p] += 1
FULL = '--full-names' in sys.argv
SHORT = short_names(people)
assert len(set(SHORT.values())) == len(people), 'two people would share a published name'
json.dump(dict(sorted((SHORT[p], p) for p in people)), open(os.path.join(PRIVATE, 'names.json'), 'w'), indent=1)
pub = (lambda p: p) if FULL else SHORT.get
leaks = [p for p in people if '@' in p or re.search(r'\.(edu|com|org)\b', p)]
assert not leaks, f'email addresses would be published as names: {leaks}'
idx = {p: i for i, p in enumerate(people)}
nodes = []
for p in people:
    r = roster.get(p)
    nodes.append(dict(name=pub(p), cls=COH.get(r['cohort'], 'Other') if r else 'Graduate',
                      grade=r['grade'] if r and r['grade'] != 'Unknown' else ('Graduated' if not r else ''),
                      current=bool(r)))
chats = sorted(([idx[x['s']], idx[x['t']], x['date'], CL[x['sem']]] for x in ch), key=lambda e: e[2])
built = max(c[2] for c in chats)
json.dump(dict(nodes=nodes, chats=chats, built=built), open(OUT, 'w'), separators=(',', ':'))
# full-name copy of exactly what was published, for report.py (private, never deployed)
json.dump([dict(s=x['s'], t=x['t'], date=x['date'], cls=CL[x['sem']], idx=x.get('idx')) for x in ch],
          open(os.path.join(PRIVATE, 'scoped_chats.json'), 'w'))
n_new = len({x['s'] for x in ch})
print(len(chats), 'chats |', len(nodes), 'people |', n_new, 'new members |',
      dict(C.Counter(CL[x['sem']] for x in ch)), '| graduates', sum(not n['current'] for n in nodes),
      f'| {manual_used} screenshot chats still needed | through {built}')
