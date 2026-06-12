import urllib.request
try:
    content = urllib.request.urlopen('http://127.0.0.1:8877/').read().decode('utf-8')
    print("Fast model found:", 'Fast model' in content)
except Exception as e:
    print("Error:", e)
