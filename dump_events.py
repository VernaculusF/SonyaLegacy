import sqlite3
c = sqlite3.connect('/home/jester-sonya/.sonya/sonya_substrate.db')
for row in c.execute("SELECT seq, kind, channel, created_at, payload_json FROM continuity_events ORDER BY seq DESC LIMIT 20;").fetchall():
    print(row)
