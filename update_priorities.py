import sqlite3

db_path = '/home/jester-sonya/.sonya/sonya_substrate.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Set all openrouter accounts to priority -1
c.execute("UPDATE provider_accounts SET priority = -1 WHERE provider_id = 'openrouter'")

# Set sonyamain to priority 100
c.execute("UPDATE provider_accounts SET priority = 100 WHERE name = 'sonyamain'")

conn.commit()
print("Account priorities updated successfully.")

for row in c.execute("SELECT account_id, name, priority FROM provider_accounts WHERE provider_id = 'openrouter' ORDER BY priority DESC"):
    print(row)
