"""Rebuild work/roster.json and work/address_map.json from the chapter contact sheet.

    python3 roster.py ["/path/to/Winter 2027 PSE Current Member Contact Info.xlsx"]

Defaults to roster_xlsx in config.json. The sheet layout is the one PSE uses: a cohort heading row
("Omega '26"), then one row per member with name, grade, ?, email, major. Gender labels carry over
from the previous roster by name; new members get 'Unknown' (only the gender slides use them).
Address matches from the previous build are kept, so nicknames and graduates stay resolved.
"""
import json, re, sys, os, collections as C, unicodedata
from common import data, CFG

sys.path.insert(0, data('deps'))
import openpyxl  # vendored in work/deps


def norm(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', s).lower())


def main(xlsx):
    old = json.load(open(data('roster.json'))) if os.path.exists(data('roster.json')) else {}
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    r, co = {}, ''
    for cells in wb.worksheets[0].iter_rows(values_only=True):
        if not cells:
            continue
        cells = list(cells) + [None] * 10
        n = str(cells[0] or '').strip()
        if not n or n == '-':
            continue
        if re.match(r"^(\w+) '\d\d$", n) or re.match(r'^(Sigma|Tau|Upsilon|Phi|Chi|Psi|Omega|Exchange) ', n):
            co = n
            continue
        newest = CFG['classes'][-1]['cohort']
        r[n] = {'cohort': co, 'grade': cells[1] or 'Unknown', 'major': str(cells[4] or 'Unknown').strip(),
                'email': str(cells[3] or '').lower().strip(),
                'role_now': 'new' if co == newest else 'exchange' if co.startswith('Exchange') else 'official',
                'gender': old.get(n, {}).get('gender', 'Unknown')}
    unknown_cohorts = sorted({v['cohort'] for v in r.values()} - set(CFG['older_cohorts']) -
                             {c['cohort'] for c in CFG['classes']} - {c for c in (v['cohort'] for v in r.values()) if c.startswith('Exchange')})
    json.dump(r, open(data('roster.json'), 'w'), indent=2)

    amap = json.load(open(data('address_map.json'))) if os.path.exists(data('address_map.json')) else {}
    amap.update({v['email']: n for n, v in r.items() if v['email']})
    lookup = {norm(n): n for n in r}
    for a, names in json.load(open(data('header_identities.json'))).items():
        c = {lookup[norm(n)] for n in names if norm(n) in lookup}
        if a not in amap and len(c) == 1:
            amap[a] = c.pop()
    json.dump(amap, open(data('address_map.json'), 'w'), indent=2)

    print(f'roster {len(r)}', dict(C.Counter(v['cohort'] for v in r.values())), f'| {len(amap)} known addresses')
    if unknown_cohorts:
        print('  add these cohorts to config.json (older_cohorts or classes):', unknown_cohorts)
    missing = [n for n, v in r.items() if v['gender'] == 'Unknown' and v['role_now'] != 'exchange']
    if missing:
        print(f'  {len(missing)} members without a gender label (only matters for the gender slides)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else data(CFG['roster_xlsx']))  # default lives in the data folder
