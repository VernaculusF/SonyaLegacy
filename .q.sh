cd ~/Sonya
sleep 60
.venv/bin/python -c "
import sqlite3, json, os
c = sqlite3.connect('/home/jester-sonya/.sonya/sonya_substrate.db')
print('=== events seq>=17497 (capability test trace) ===')
for r in c.execute(\"SELECT seq, kind, payload_json FROM continuity_events WHERE seq >= 17497 ORDER BY seq\"):
    seq, k, pj = r
    try: p = json.loads(pj or '{}')
    except: p = {}
    txt = (p.get('text') or p.get('content') or p.get('arg') or p.get('observation') or p.get('marker') or '')[:140]
    tool = p.get('tool', '')
    extra = f' tool={tool}' if tool else ''
    print(f'{seq:5} {k[:42]:42}{extra} {txt}')
print()
print('=== plugin files ===')
plugins_dir = '/home/jester-sonya/Sonya/src/sonya/tools/plugins'
for f in sorted(os.listdir(plugins_dir)):
    if f.endswith('.py') and f != '__init__.py':
        path = os.path.join(plugins_dir, f)
        print(f'  {f}: {os.path.getsize(path)} bytes')
print()
print('=== email_reader.py if exists ===')
ep = os.path.join(plugins_dir, 'email_reader.py')
if os.path.exists(ep):
    print(open(ep).read())
else:
    print('NOT FOUND')
"
