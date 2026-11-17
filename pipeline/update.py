"""One command to refresh everything after a new export.

    python3 update.py                                  # rebuild from what is already stored
    python3 update.py ~/Downloads/takeout-*.zip        # add new Gmail export(s) first
    python3 update.py --roster new_contact_sheet.xlsx  # also refresh the member list

Then check private/report.md for the deck numbers, look at the site locally
(python3 -m http.server -d ../public), and commit public/data.json to redeploy.
"""
import os, subprocess, sys
from common import BUILD, PUBLIC, HERE

args = sys.argv[1:]
roster = None
if '--roster' in args:
    i = args.index('--roster'); roster = args[i + 1]; del args[i:i + 2]

def run(*cmd):
    print('$', ' '.join(cmd), flush=True)
    subprocess.run([sys.executable, *cmd], cwd=HERE, check=True)

if args:
    run('ingest.py', *args)
if roster:
    run('roster.py', roster)
notes, chats = os.path.join(BUILD, 'notes.json'), os.path.join(BUILD, 'chats.json')
run('extract.py', notes)
run('clean.py', notes, chats)
run('export.py', chats, os.path.join(PUBLIC, 'data.json'))
run('report.py')
run('deck_stats.py')
run('site_text.py')
