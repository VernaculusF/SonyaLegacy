import sqlite3
c = sqlite3.connect("/home/jester-sonya/.sonya/sonya_substrate.db")
rows = c.execute("SELECT seq, kind, substr(payload_json,1,120) FROM continuity_events ORDER BY seq DESC LIMIT 24").fetchall()
for r in reversed(rows):
    print(r[0], r[1], "|", r[2])
