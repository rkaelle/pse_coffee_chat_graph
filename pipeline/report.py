"""Recompute the deck numbers that move when new chats arrive, and show what changed since the last run.

    python3 report.py

Reads private/scoped_chats.json (written by export.py) and work/roster.json. Writes
private/report.json and private/report.md (full names, so both stay local). Each line names the
slide it feeds in the current Google deck.
"""
import json, os, statistics as S, collections as C
from common import data, PRIVATE, CLASSES

SKIP = set(json.load(open(os.path.join(PRIVATE, 'overrides.json'))).get('not_on_no_chat_list', [])) if os.path.exists(os.path.join(PRIVATE, 'overrides.json')) else set()

ch = json.load(open(os.path.join(PRIVATE, 'scoped_chats.json')))
roster = json.load(open(data('roster.json')))
new_cls = [c['name'] for c in CLASSES]
latest = new_cls[-1]
latest_cohort = CLASSES[-1]['cohort']
through = max(x['date'] for x in ch)

# --- network (slide 4) ---
people = sorted({x['s'] for x in ch} | {x['t'] for x in ch})
adj = C.defaultdict(set)
for x in ch:
    adj[x['s']].add(x['t']); adj[x['t']].add(x['s'])
dists = []
for p in people:
    d, frontier = {p: 0}, [p]
    while frontier:
        nxt = []
        for u in frontier:
            for v in adj[u]:
                if v not in d:
                    d[v] = d[u] + 1; nxt.append(v)
        frontier = nxt
    dists += [v for q, v in d.items() if q > p]
senders = {x['s'] for x in ch}
grads = {p for p in people if p not in roster}
net = {
    'chats': len(ch), 'new_members': len(senders), 'other_members': len(people) - len(senders),
    'people': len(people), 'graduated_seniors': len(grads),
    'chats_with_graduates': sum(x['t'] in grads for x in ch),
    'avg_steps': round(sum(dists) / len(dists), 2), 'pct_within_two': round(100 * sum(d <= 2 for d in dists) / len(dists)),
    'max_steps': max(dists), 'per_class': dict(C.Counter(x['cls'] for x in ch)),
}

# --- latest class vs current brothers (slides 17-21) ---
brothers = [n for n, v in roster.items() if v['cohort'] != latest_cohort and not v['cohort'].startswith('Exchange')]
lat = [x for x in ch if x['cls'] == latest]
per_b = C.Counter(x['t'] for x in lat if x['t'] in brothers)
counts = sorted((per_b.get(b, 0) for b in brothers), reverse=True)
half = len(counts) // 2
last_any = {}
for x in ch:
    last_any[x['t']] = max(last_any.get(x['t'], ''), x['date'])
def short_cohort(b):
    return roster[b]['cohort'].split(" '")[0]
none_yet = sorted((b for b in brothers if not per_b.get(b) and b not in SKIP), key=lambda b: (last_any.get(b, ''), b))
latest_view = {
    'brothers': len(brothers), 'reached': sum(1 for b in brothers if per_b.get(b) or b in SKIP),
    'no_chat_yet': len(none_yet), 'just_one': sum(1 for b in brothers if per_b.get(b) == 1),
    'median_per_brother': S.median(counts), 'avg_per_brother': round(sum(counts) / len(counts), 1),
    'pct_to_bottom_half': round(100 * sum(counts[half:]) / max(1, sum(counts))),
    'top': [[b, short_cohort(b), n] for b, n in per_b.most_common(6)],
    'no_chat_list': [[b, f"{short_cohort(b)}, {roster[b]['grade']}", last_any.get(b, 'none on record')] for b in none_yet],
}

# --- reach by class distance (slide 6) ---
order = [k for k in sorted({v['cohort'] for v in roster.values() if not v['cohort'].startswith('Exchange')},
                           key=lambda c: int(c.split("'")[1]) * 2 + (c.split()[0] in ('Sigma', 'Upsilon', 'Chi', 'Omega')))]
pairs = {(x['s'], x['t']) for x in ch}
gen = {}
for c in CLASSES:
    members = [n for n, v in roster.items() if v['cohort'] == c['cohort']]
    i = order.index(c['cohort'])
    row = {}
    for up in range(1, i + 1):
        coh = order[i - up]
        bros = [n for n, v in roster.items() if v['cohort'] == coh]
        tot = len(members) * len(bros)
        if tot:
            row[f"{up} up ({coh.split(' ')[0]})"] = round(100 * sum((m, b) in pairs for m in members for b in bros) / tot)
    gen[c['name']] = row

# --- most connected brother (slides 10, 22) ---
met = C.defaultdict(set)
for x in ch:
    met[x['t']].add(x['s'])
top = sorted(met.items(), key=lambda kv: -len(kv[1]))[:3]
most = [[b, len(s)] for b, s in top]

R = dict(through=through, network=net, latest_class=latest, latest=latest_view, reach_by_class_distance=gen,
         most_new_members_met=most)
prev_p = os.path.join(PRIVATE, 'report.json')
prev = json.load(open(prev_p)) if os.path.exists(prev_p) else None

def changes(a, b, path=''):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            out += changes(a[k], b.get(k), f'{path}.{k}' if path else k)
    elif isinstance(a, list) and isinstance(b, list) and a and isinstance(a[0], list):
        A, B = {json.dumps(r) for r in a}, {json.dumps(r) for r in b}
        out += [f'{path}: added {r}' for r in sorted(A - B)] + [f'{path}: removed {r}' for r in sorted(B - A)]
    elif a != b:
        out.append(f'{path}: {b} -> {a}')
    return out

L = [f'# Deck numbers through {through}', '',
     '## Slide 4: network',
     f"- {net['chats']:,} chats from {net['new_members']} new members to {net['other_members']} other members",
     f"- {net['chats_with_graduates']} chats with {net['graduated_seniors']} graduated seniors | {net['people']} people",
     f"- {net['avg_steps']:.2f} average steps | {net['pct_within_two']}% of pairs within two | {net['max_steps']} steps at most",
     f"- per class: {net['per_class']}", '',
     '## Slide 6: share of pairs that chatted, by class distance']
L += [f"- {k}: " + ', '.join(f'{a} {b}%' for a, b in v.items()) for k, v in gen.items()]
lv = latest_view
L += ['', f'## Slides 17-21: {latest} and the {lv["brothers"]} current brothers',
      f"- {latest} has reached {lv['reached']} of {lv['brothers']} | {lv['no_chat_yet']} with no {latest} chat | {lv['just_one']} with just one",
      f"- median {lv['median_per_brother']} {latest} chats per brother (average {lv['avg_per_brother']}) | {lv['pct_to_bottom_half']}% to the bottom half",
      '- most chatted: ' + ', '.join(f'{b} ({c}) {n}' for b, c, n in lv['top']),
      '- no chat yet (name, class, last chat with any new member):']
L += [f'  - {b}, {c}, {d}' for b, c, d in lv['no_chat_list']]
L += ['', '## Slides 10, 22: most new members met', *(f'- {b}: {n}' for b, n in most)]
if prev:
    diff = changes(R, prev)
    L += ['', f"## Changed since the last run ({prev['through']})"] + ([f'- {d}' for d in diff] or ['- nothing'])
json.dump(R, open(prev_p, 'w'), indent=1)
open(os.path.join(PRIVATE, 'report.md'), 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
