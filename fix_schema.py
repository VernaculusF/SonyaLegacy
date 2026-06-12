import sys
with open('src/sonya/state/schema.sql', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'embedded_at TEXT NOT NULL DEFAULT \'\'' in line:
        # replace the newline with comma and newline, then add media_phash
        new_lines.append(line.rstrip('\\r\\n') + ',\n')
        new_lines.append('    media_phash TEXT NOT NULL DEFAULT \'\'\n')
    else:
        new_lines.append(line)

with open('src/sonya/state/schema.sql', 'w', encoding='utf-8', newline='') as f:
    f.writelines(new_lines)
print("Done schema")
