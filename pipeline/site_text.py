"""Refresh the few numbers written into the site's HTML and JS (link preview text, about box, tips).

Run by update.py after report.py. Leaves the files untouched when nothing changed.
"""
import json, os, re, datetime as dt
from common import PUBLIC, PRIVATE

R = json.load(open(os.path.join(PRIVATE, 'report.json')))
net, lv, latest = R['network'], R['latest'], R['latest_class']
d = json.load(open(os.path.join(PUBLIC, 'data.json')))
# the site counts reach from the emails alone, so it ignores report.py's manual "reached" list
recv = {}
for s, t, day, cls in d['chats']:
    recv.setdefault(t, set()).add(s)
through = dt.date.fromisoformat(R['through'])
nice = f"{through:%B} {through.day}, {through.year}"

def sub(path, pairs):
    p = os.path.join(PUBLIC, path)
    s = old = open(p).read()
    for pat, rep in pairs:
        s, n = re.subn(pat, rep, s)
        if not n:
            print(f'  {path}: pattern not found, update by hand: {pat}')
    if s != old:
        open(p, 'w').write(s)
        print(f'  updated {path}')

sub('index.html', [
    (r'[\d,]+ coffee chats among \d+ members', f"{net['chats']:,} coffee chats among {net['people']} members"),
    (r'all [\d,]+ of those emails', f"all {net['chats']:,} of those emails"),
    (r'the \d+ seniors who have since graduated', f"the {net['graduated_seniors']} seniors who have since graduated"),
    (rf'{latest} runs through [A-Z][a-z]+ \d+, \d{{4}}', f'{latest} runs through {nice}'),
])
reached = lv['reached'] - len(json.load(open(os.path.join(PRIVATE, 'overrides.json'))).get('not_on_no_chat_list', []))
# always rewrite, so the date moves forward even when the count does not
sub('app.js', [(r'reached \d+ of \d+ current brothers[^<]*<', f"reached {reached} of {lv['brothers']} current brothers through {through:%B} {through.day}.<")])
sub('app.js', [(r"'[\d,]+ coffee chats among \d+'", f"'{net['chats']:,} coffee chats among {net['people']}'")])  # link-preview card: re-render og.png after this
top = R['most_new_members_met']
sub('app.js', [(r'The president met \d+ of \d+ new members, [a-z]+ more than anyone else',
                f"The president met {top[0][1]} of {net['new_members']} new members, "
                f"{['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'][min(12, top[0][1] - top[1][1])]} more than anyone else")])
