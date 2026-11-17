"""Shared paths and settings. Edit config.json (public settings) or ../private/overrides.json (names)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json')))
DATA = os.path.normpath(os.path.join(HERE, CFG['data_dir']))   # raw mail + roster, never committed
PRIVATE = os.path.normpath(os.path.join(HERE, '..', 'private'))  # full-name outputs, never committed
PUBLIC = os.path.normpath(os.path.join(HERE, '..', 'public'))
BUILD = os.path.join(DATA, 'build')
os.makedirs(PRIVATE, exist_ok=True)
os.makedirs(BUILD, exist_ok=True)


def data(name):
    return os.path.join(DATA, name)


def overrides():
    """Manual chats and name fixes. They hold real names and addresses, so they live in private/."""
    p = os.path.join(PRIVATE, 'overrides.json')
    o = json.load(open(p)) if os.path.exists(p) else {}
    return dict(manual_chats=o.get('manual_chats', []), name_fix=o.get('name_fix', {}),
                last_name=o.get('last_name', {}))


CLASSES = CFG['classes']
SEM_TO_CLASS = {c['semester']: c['name'] for c in CLASSES}
COHORT_SEM = dict(CFG['older_cohorts'], **{c['cohort']: c['semester'] for c in CLASSES})
COHORT_SHORT = {k: k.split(" '")[0] for k in COHORT_SEM}
