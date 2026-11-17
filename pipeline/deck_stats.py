"""Every deck number that report.py does not cover: gender, timing, wording, superlatives, chart data.

    python3 deck_stats.py

Reads private/scoped_chats.json (written by export.py), the cleaned emails in work/build/chats.json
and work/roster.json. Writes private/deck_stats.json (full names, so it stays local). The
definitions match the ones used to build the deck in November 2026; each key names its slide.
"""
import json, os, re, random, itertools as IT, statistics as st, datetime as dt, collections as C
from common import data, BUILD, PRIVATE, CLASSES

roster = json.load(open(data('roster.json')))
OV = json.load(open(os.path.join(PRIVATE, 'overrides.json')))
emails = {x['idx']: x for x in json.load(open(os.path.join(BUILD, 'chats.json')))}
manual = {(m[0], m[1], m[2]): m[3:] for m in OV.get('manual_chats', [])}
cl = [c['name'] for c in CLASSES]
latest = cl[-1]

ch = []
for x in json.load(open(os.path.join(PRIVATE, 'scoped_chats.json'))):
    if x.get('idx') is not None:
        e = emails[x['idx']]
        ts, body = e['ts'], e['body']
    else:  # known only from a screenshot: use its send time and visible text when recorded
        extra = manual.get((x['s'], x['t'], x['date']), [])
        ts = extra[0] if extra else x['date'] + 'T12:00:00-05:00'
        body = extra[1] if len(extra) > 1 else ''
    ch.append(dict(x, ts=ts, body=body))


def core(b):
    b = re.split(r'(?m)^\s*(Best|Sincerely|Regards|Thanks,|Thank you,|Warm|All the best|Cheers|Respectfully|--\s*$)', b)[0]
    b = re.split(r'(?m)^On .{5,200}wrote:', b)[0]
    return re.sub(r'\[image:[^\]]*\]', '', b).strip()


for x in ch:
    x['d'] = dt.date.fromisoformat(x['date'])
    x['t_dt'] = dt.datetime.fromisoformat(x['ts'])
    x['c'] = core(x['body'])
    x['w'] = len(x['c'].split())
by = C.defaultdict(list)
for x in ch:
    by[(x['cls'], x['s'])].append(x)
for v in by.values():
    v.sort(key=lambda x: x['ts'])
    for i, x in enumerate(v):
        x['ord'], x['frac'] = i + 1, i / max(1, len(v) - 1)
d0 = {c: min(x['d'] for x in ch if x['cls'] == c) for c in cl}
for x in ch:
    x['wk'] = (x['d'] - d0[x['cls']]).days // 7
G = {n: v['gender'] for n, v in roster.items() if v['gender'] in ('M', 'W')}
G2 = dict(G, **OV.get('graduate_gender', {}))
F = {'through': max(x['date'] for x in ch), 'n': len(ch), 'per_class': dict(C.Counter(x['cls'] for x in ch)),
     'latest_weeks_in': (max(x['d'] for x in ch if x['cls'] == latest) - d0[latest]).days // 7 + 1}

# --- slides 3, 8: same-gender share by chat number, and the same-gender share of who is left ---
bins = [(1, 10), (11, 20), (21, 30), (31, 99)]
def share(rows):
    l = [x for x in rows if x['s'] in G2 and x['t'] in G2]
    return round(100 * sum(G2[x['s']] == G2[x['t']] for x in l) / len(l), 1) if l else None
F['s8_fade_all'] = [share([x for x in ch if a <= x['ord'] <= b]) for a, b in bins]
F['s8_fade_by_class'] = {c: [share([x for x in ch if a <= x['ord'] <= b and x['cls'] == c]) for a, b in bins] for c in cl}
F['s8_fade_n'] = {c: [sum(1 for x in ch if a <= x['ord'] <= b and x['cls'] == c and x['s'] in G2 and x['t'] in G2) for a, b in bins] for c in cl}
tp = {c: {x['t'] for x in ch if x['cls'] == c and x['t'] in G2} for c in cl}
pool = []
for a, b in bins:
    v = []
    for x in ch:
        if a <= x['ord'] <= b and x['s'] in G2 and x['t'] in G2:
            seen = {y['t'] for y in by[(x['cls'], x['s'])][:x['ord'] - 1]}
            p = [t for t in tp[x['cls']] if t not in seen]
            v.append(sum(G2[t] == G2[x['s']] for t in p) / len(p))
    pool.append(round(100 * st.mean(v), 1))
F['s8_pool'] = pool

# --- slides 3, 9: same gender / same major against 1,000 reshuffles that keep each person's chat count ---
def mg(m):
    m = m.lower()
    return 'Business' if 'business' in m else 'Econ' if 'econ' in m else 'Other'
MJ = {n: mg(v['major']) for n, v in roster.items()}
def lift(rows, fn, seed):
    rnd = random.Random(seed)
    s = [x['s'] for x in rows]; t = [x['t'] for x in rows]
    o = sum(fn(a, b) for a, b in zip(s, t)); nl = []
    for _ in range(1000):
        rnd.shuffle(t); nl.append(sum(fn(a, b) for a, b in zip(s, t)))
    return dict(actual=round(100 * o / len(s), 1), random=round(100 * st.mean(nl) / len(s), 1),
                pts=round(100 * (o - st.mean(nl)) / len(s), 1), z=round((o - st.mean(nl)) / st.pstdev(nl), 1), n=len(s))
F['s9_gender'] = lift([x for x in ch if x['s'] in G2 and x['t'] in G2], lambda a, b: G2[a] == G2[b], 4)
F['s9_major'] = lift([x for x in ch if x['s'] in MJ and x['t'] in MJ], lambda a, b: MJ[a] == MJ[b], 5)

# --- slides 3, 10, 22: distinct new members met, across all classes ---
dp = C.defaultdict(set)
for x in ch:
    dp[x['t']].add(x['s'])
F['s10_most_met'] = [[k, len(v)] for k, v in sorted(dp.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:12]]
F['new_members'] = len({x['s'] for x in ch})

# --- slide 11: does popularity carry from one class to the next ---
sc = {c: C.Counter(x['t'] for x in ch if x['cls'] == c) for c in cl}
def spear(a, b):
    ks = [k for k in a if k in b]
    ra = {k: i for i, k in enumerate(sorted(ks, key=a.get))}; rb = {k: i for i, k in enumerate(sorted(ks, key=b.get))}
    n = len(ks)
    return [round(1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in ks) / (n * (n * n - 1)), 2), n]
F['s11_rank_corr'] = {f'{a}->{b}': spear(sc[a], sc[b]) for a, b in zip(cl, cl[1:])}
F['s10_top_ten_overlap'] = {f'{a}->{b}': len({k for k, _ in sc[a].most_common(10)} & {k for k, _ in sc[b].most_common(10)}) for a, b in zip(cl, cl[1:])}

# --- slide 13: send times ---
hm = [[0] * 24 for _ in range(7)]
for x in ch:
    hm[x['t_dt'].weekday()][x['t_dt'].hour] += 1
wd = [sum(r) for r in hm]
F['s13_heat'] = hm
F['s13_thu_fri_pct'] = round(100 * (wd[3] + wd[4]) / len(ch))
F['s13_at_8am'] = sum(x['t_dt'].hour == 8 and x['t_dt'].minute == 0 for x in ch)
bd = C.Counter((x['t'], x['date']) for x in ch)
F['s13_share_a_day_pct'] = round(100 * sum(v for v in bd.values() if v >= 2) / len(ch))

# --- slide 14: exclamation points by week (weeks with 20+ emails) ---
F['s14_exclaim_by_week'] = {c: [[w + 1, round(100 * sum('!' in x['c'] for x in ch if x['cls'] == c and x['wk'] == w) / n), n]
                                for w, n in sorted(C.Counter(x['wk'] for x in ch if x['cls'] == c).items()) if n >= 20] for c in cl}

# --- slide 15: what the emails mention ---
acts = dict(Walks=r'\bwalk', Basketball='basketball', Pickleball='pickleball', **{'Coffee itself': r'\bcoffee\b'}, Golf=r'\bgolf',
            Cooking=r'\bcook', **{'Winter Garden': 'Winter Garden'}, Tennis='tennis', **{'Lunch or dinner': r'\blunch|\bdinner|\bbrunch'},
            Coloring='coloring', Starbucks='Starbucks')
nochat = lambda t: re.sub(r'(?i)coffee chats?', '', t)  # "coffee" outside the phrase "coffee chat"
F['s15_mentions'] = {k: sum(bool(re.search(p, nochat(x['c']), re.I)) for x in ch) for k, p in acts.items()}
F['s15_coffee_pct'] = round(100 * sum(bool(re.search(r'\bcoffee\b', re.sub(r'(?i)coffee chats?', '', x['c']), re.I)) for x in ch) / len(ch), 1)

# --- slide 16: the latest class against earlier ones at the same stage ---
def met_by_week(c, weeks=6):
    ppl = {x['s'] for x in ch if x['cls'] == c}
    return [round(st.mean(len({x['t'] for x in ch if x['cls'] == c and x['s'] == p and x['wk'] <= w}) for p in ppl), 1) for w in range(weeks)]
F['s16_met_by_week'] = {c: met_by_week(c) for c in cl}
# a partial week is shown once it has five days of data (the latest class's last week is usually partial)
days = (max(x['d'] for x in ch if x['cls'] == latest) - d0[latest]).days
F['s16_weeks_shown'] = days // 7 + (1 if days % 7 >= 4 else 0)
lat = [x for x in ch if x['cls'] == latest]
upper = lambda x: roster.get(x['t'], {}).get('grade') in ('Junior', 'Senior')
F['s16_upper_pct'] = round(100 * sum(map(upper, lat)) / len(lat))
per = [sum(map(upper, v)) / len(v) for k, v in by.items() if k[0] == latest]
F['s16_clear_two_thirds'] = [sum(s >= 2 / 3 for s in per), len(per)]

# --- slides 17, 18: chats per current brother ---
brothers = [n for n, v in roster.items() if v.get('role_now') == 'official']
lc = C.Counter(x['t'] for x in lat)
coh = C.defaultdict(list)
for b in brothers:
    coh[roster[b]['cohort'].split(" '")[0]].append(lc.get(b, 0))
# rounded half up, as the chart shows it
F['s17_per_brother_by_class'] = sorted(([k, round(st.mean(v) + 1e-9, 1), len(v)] for k, v in coh.items()), key=lambda r: -r[1])
F['s18_histogram'] = sorted(C.Counter(lc.get(b, 0) for b in brothers).items())

# --- slide 22: superlatives ---
F['s22_longest'] = sorted(([x['w'], x['s'], x['t'], x['cls']] for x in ch), reverse=True)[:3]
F['s22_busiest_day'] = [[t, d, n] for (t, d), n in bd.most_common() if n == bd.most_common(1)[0][1]]
prev = cl[-2] if len(cl) > 1 else None
prev_cohort = CLASSES[-3]['cohort'] if len(CLASSES) > 2 else None  # pledged one year before the latest class
F['s22_fastest_rising'] = sorted(([b, n] for b, n in lc.items() if roster.get(b, {}).get('cohort') == prev_cohort), key=lambda r: -r[1])[:3]
def first_sentence(c):  # after the greeting
    b = re.sub(r'^.{0,45}?[,\n]\s*', '', c.replace('\n', ' '), count=1)
    return re.sub(r'\W+', ' ', re.split(r'(?<=[.!?])\s', b)[0].lower()).strip()
op = C.Counter(first_sentence(x['c']) for x in lat).most_common(1)[0]
F['s22_opener'] = [op[0], op[1], len(lat)]
tw = []
for c in cl[:-1]:
    for a, b in IT.combinations(sorted({x['s'] for x in ch if x['cls'] == c}), 2):
        A, B = {x['t'] for x in by[(c, a)]}, {x['t'] for x in by[(c, b)]}
        tw.append([len(A & B), a, b, c])
F['s22_twins'] = sorted(tw, reverse=True)[:2]

# --- notes on slides 6, 13, 18, 19 ---
order = sorted({v['cohort'] for v in roster.values() if not v['cohort'].startswith('Exchange')},
               key=lambda c: int(c.split("'")[1]) * 2 + (c.split()[0] in ('Sigma', 'Upsilon', 'Chi', 'Omega')))
size = C.Counter(v['cohort'] for v in roster.values())
two_up = {}
for c in CLASSES:
    i = order.index(c['cohort'])
    above = order[:i]
    hits = 0
    members = sorted({x['s'] for x in ch if x['cls'] == c['name']})
    for m in members:
        met = C.Counter(roster[t]['cohort'] for t in {x['t'] for x in ch if x['s'] == m and x['cls'] == c['name']} if t in roster)
        best = max(above, key=lambda k: met[k] / size[k]) if above else None
        hits += best == (order[i - 2] if i >= 2 else None)
    two_up[c['name']] = [hits, len(members)]
F['s6_top_class_two_up'] = two_up
lag = C.defaultdict(list)
for x in ch:
    m = re.search(r'(?<!\d)(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?(?!\d)', emails[x['idx']]['subject'] if x.get('idx') is not None else '')
    if m:
        try:
            v = (x['d'] - dt.date(x['d'].year, int(m[1]), int(m[2]))).days
            if 0 <= v <= 14:
                lag[x['cls']].append(v)
        except ValueError:
            pass
F['s13_within_a_day_pct'] = {c: [round(100 * sum(v <= 1 for v in lag[c]) / len(lag[c])), len(lag[c])] for c in cl if lag[c]}
F['s18_eleven_plus'] = sum(lc.get(b, 0) >= 11 for b in brothers)
F['s18_prev2_median'] = st.median(lc.get(b, 0) for b in brothers if roster[b]['cohort'] == prev_cohort)
F['s19_just_one'] = sorted((b for b in brothers if lc.get(b, 0) == 1), key=lambda b: max((x['date'] for x in ch if x['t'] == b), default=''), reverse=True)
F['s8_raw_same_gender'] = {c: share([x for x in ch if x['cls'] == c]) for c in cl}

json.dump(F, open(os.path.join(PRIVATE, 'deck_stats.json'), 'w'), indent=1, default=str)
for k, v in F.items():
    if k != 's13_heat':
        print(k, json.dumps(v, default=str)[:400])
