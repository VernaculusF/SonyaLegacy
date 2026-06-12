import sqlite3
c = sqlite3.connect('/home/jester-sonya/.sonya/sonya_substrate.db')
for row in c.execute("SELECT key_id, name, status, last_error FROM provider_keys WHERE key_id='pk-a2c231ed8a40'"):
    print(row)
