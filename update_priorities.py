import sqlite3

db_path = '/home/jester-sonya/.sonya/sonya_substrate.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Set all openrouter keys to priority -1
c.execute("UPDATE provider_keys SET priority = -1 WHERE provider = 'openrouter'")

# Set sonyamain to priority 100
c.execute("UPDATE provider_keys SET priority = 100 WHERE key_id = 'pa-f07374aa9f74'")

conn.commit()
print("Priorities updated successfully.")

for row in c.execute("SELECT key_id, name, priority FROM provider_keys WHERE provider = 'openrouter' ORDER BY priority DESC"):
    print(row)
