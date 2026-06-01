import sys
sys.path.insert(0, 'src')
from sonya.state.substrate import Substrate
s = Substrate.open('/home/jester-sonya/.sonya/sonya_substrate.db')
rows = s.connection.execute("SELECT key_id, name, provider, model, slot, status FROM provider_keys WHERE provider='kr'").fetchall()
for r in rows:
    print(r)
s.close()
