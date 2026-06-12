import sys
with open('src/sonya/state/migrations.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if '_add_column_if_missing(conn, "episodic_events", "retention_policy", "TEXT NOT NULL DEFAULT \'\'")' in line:
        new_lines.append('    _add_column_if_missing(conn, "episodic_events", "media_phash", "TEXT NOT NULL DEFAULT \'\'")\n')

with open('src/sonya/state/migrations.py', 'w', encoding='utf-8', newline='') as f:
    f.writelines(new_lines)
print("Done migrations")
