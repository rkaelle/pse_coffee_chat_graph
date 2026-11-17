"""Rebuild every member->brother thank-you note from the raw mailbox parse, across all years."""
import json, re, collections as C, email.utils, sys
from common import data
OUT = sys.argv[1]
ms = [json.loads(l) for l in open(data('messages.jsonl'))]
PD = 'pseprofdev'

def addrs(s):
    return [(n.strip(), a.lower().strip()) for n, a in email.utils.getaddresses([s or '']) if a]

def parse_forward(m):
    """Return (from, to, date, subject, body) of the note inside a Fwd, or None."""
    b = m['body']
    mt = re.search(r'From:\s*(.+?)\n(?:.*\n)*?\s*Date:\s*(.+?)\n\s*Subject:\s*(.+?)\n\s*To:\s*(.+?)\n', b)
    if not mt:
        return None
    return mt.group(1), mt.group(4), mt.group(2), mt.group(3), b[mt.end():]

recs = []
for m in ms:
    subj = m['subject'] or ''
    frm = addrs(m['from'])
    if not frm or PD in frm[0][1]:
        continue
    if re.match(r'(?i)\s*re:', subj):
        continue
    fname, faddr = frm[0]
    body, date, forwarded = m['body'], m['date'], False
    tos = addrs(m['to'])
    if re.match(r'(?i)\s*fwd?:', subj):
        fw = parse_forward(m)
        if not fw:
            continue
        forwarded = True
        subj, body = fw[3], fw[4]
        tos = addrs(fw[1].replace('mailto:', ''))
        ff = addrs(fw[0])
        if ff and ff[0][1] != faddr:
            continue  # forwarding someone else's mail, not their own note
        try:
            d = email.utils.parsedate_to_datetime(re.sub(r'\s+at\s+', ' ', fw[2]) + ' -0400')
            date = d.isoformat()
        except Exception:
            pass
    tos = [t for t in tos if PD not in t[1] and t[1] != faddr]
    if len(tos) != 1:
        continue
    tname, taddr = tos[0]
    head = subj + ' ' + body[:500]
    if not re.search(r'(?i)coff?e|chat|interview|thank|meet|call|spoke|speak|talk', head):
        continue
    recs.append(dict(idx=m['index'], date=date, sender=fname, saddr=faddr, target=tname, taddr=taddr,
                     subject=subj, body=body, forwarded=forwarded, labels=m['labels']))

print(len(recs), 'one-to-one notes')
json.dump(recs, open(OUT, 'w'))
