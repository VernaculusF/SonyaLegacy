import sqlite3
import json

conn = sqlite3.connect('/home/jester-sonya/.sonya/sonya_substrate.db')
cursor = conn.cursor()

# Set defaults
cursor.execute('''
    UPDATE provider_settings 
    SET active_provider = 'openrouter',
        default_model = 'nvidia/nemotron-4-340b-instruct',
        default_fallback = 'google/gemma-2-27b-it',
        fast_model = 'google-ai-studio/gemma-2-27b-it',
        fast_fallback = 'kimchi/minimax-m2.7',
        deep_model = 'owl-alpha',
        deep_fallback = 'nex-agi/nex-n2-pro:free',
        vision_model = 'google-ai-studio/gemini-1.5-pro',
        vision_fallback = 'openrouter/gemini-pro-vision'
    WHERE id = 1
''')

conn.commit()
print("Updated provider_settings")
